import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException
from redis import Redis


class MemoryRateLimiter:
    def __init__(self, limit: int = 10, window: int = 60) -> None:
        self._limit = limit
        self._window = window
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.time()
        with self._lock:
            self._attempts[key] = [t for t in self._attempts[key] if now - t < self._window]
            if len(self._attempts[key]) >= self._limit:
                raise HTTPException(
                    status_code=429, detail="Muitas tentativas. Tente novamente em breve."
                )
            self._attempts[key].append(now)


class RedisRateLimiter:
    def __init__(self, redis_url: str, limit: int = 10, window: int = 60) -> None:
        self._client: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._limit = limit
        self._window = window

    def check(self, key: str) -> None:
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self._window)
        results = pipe.execute()
        if int(results[0]) > self._limit:
            raise HTTPException(
                status_code=429, detail="Muitas tentativas. Tente novamente em breve."
            )


def make_rate_limiter(
    redis_url: str | None, limit: int = 10, window: int = 60
) -> MemoryRateLimiter | RedisRateLimiter:
    if redis_url:
        return RedisRateLimiter(redis_url, limit=limit, window=window)
    return MemoryRateLimiter(limit=limit, window=window)
