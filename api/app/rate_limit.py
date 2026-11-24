import logging
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException
from redis import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class MemoryRateLimiter:
    """Janela deslizante por chave, na memória do processo: cada réplica conta a sua."""

    def __init__(self, limit: int = 10, window: int = 60) -> None:
        self._limit = limit
        self._window = window
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, limit: int | None = None, window: int | None = None) -> None:
        limit = limit or self._limit
        window_seconds = window or self._window
        now = time.time()
        with self._lock:
            self._attempts[key] = [
                attempted_at
                for attempted_at in self._attempts[key]
                if now - attempted_at < window_seconds
            ]
            if len(self._attempts[key]) >= limit:
                raise HTTPException(
                    status_code=429, detail="Muitas tentativas. Tente novamente em breve."
                )
            self._attempts[key].append(now)

    def state(self) -> str:
        """Para o /health: sem Redis, o limite é por processo."""
        return "off"


class RedisRateLimiter:
    """Contador por chave no Redis, válido entre réplicas, com janela fixa."""

    def __init__(self, redis_url: str, limit: int = 10, window: int = 60) -> None:
        # Redis travado não pendura o login (Fase 44)
        self._client: Redis = Redis.from_url(
            redis_url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2
        )
        self._limit = limit
        self._window = window
        # Redis fora não derruba login nem webhook: o limite vale por processo até voltar
        self._fallback = MemoryRateLimiter(limit=limit, window=window)

    def check(self, key: str, limit: int | None = None, window: int | None = None) -> None:
        try:
            self._check(key, limit, window)
        except RedisError as exc:
            logger.warning("redis fora: limite em memória", extra={"error": type(exc).__name__})
            self._fallback.check(key, limit, window)

    def _check(self, key: str, limit: int | None, window: int | None) -> None:
        limit = limit or self._limit
        pipeline = self._client.pipeline()
        pipeline.incr(key)
        # NX: a janela começa na primeira tentativa; renovar a cada tentativa
        # manteria a chave bloqueada para sempre sob tentativas contínuas
        pipeline.expire(key, window or self._window, nx=True)
        pipeline_results = pipeline.execute()
        attempts_in_window = int(pipeline_results[0])
        if attempts_in_window > limit:
            raise HTTPException(
                status_code=429, detail="Muitas tentativas. Tente novamente em breve."
            )

    def state(self) -> str:
        """Para o /health: "ok" ou "unreachable"."""
        try:
            self._client.ping()
        except Exception:
            return "unreachable"
        return "ok"


def make_rate_limiter(
    redis_url: str | None, limit: int = 10, window: int = 60
) -> MemoryRateLimiter | RedisRateLimiter:
    """Com Redis o limite vale entre réplicas; sem ele, por processo."""
    if redis_url:
        return RedisRateLimiter(redis_url, limit=limit, window=window)
    return MemoryRateLimiter(limit=limit, window=window)
