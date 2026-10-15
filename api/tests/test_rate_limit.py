from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.rate_limit import MemoryRateLimiter, RedisRateLimiter


def test_memoria_bloqueia_apos_limite() -> None:
    limiter = MemoryRateLimiter(limit=2, window=60)
    limiter.check("k")
    limiter.check("k")
    with pytest.raises(HTTPException) as exc:
        limiter.check("k")
    assert exc.value.status_code == 429


def test_memoria_limite_por_chamada_sobrepoe_o_padrao() -> None:
    limiter = MemoryRateLimiter(limit=1, window=60)
    limiter.check("ip", limit=3)
    limiter.check("ip", limit=3)
    limiter.check("ip", limit=3)
    with pytest.raises(HTTPException):
        limiter.check("ip", limit=3)


def test_redis_nao_renova_janela_a_cada_tentativa(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    pipe = client.pipeline.return_value
    pipe.execute.return_value = [1, True]
    monkeypatch.setattr("app.rate_limit.Redis.from_url", lambda *a, **k: client)

    RedisRateLimiter("redis://x", limit=5, window=60).check("k")

    pipe.expire.assert_called_once_with("k", 60, nx=True)


def test_redis_bloqueia_acima_do_limite(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.pipeline.return_value.execute.return_value = [6, False]
    monkeypatch.setattr("app.rate_limit.Redis.from_url", lambda *a, **k: client)

    with pytest.raises(HTTPException):
        RedisRateLimiter("redis://x", limit=5, window=60).check("k")
