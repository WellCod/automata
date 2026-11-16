"""Redis fora não derruba login nem webhook (OPS-06)."""

import pytest
from fastapi import HTTPException

from app.rate_limit import RedisRateLimiter


def test_redis_fora_cai_no_limite_em_memoria() -> None:
    # porta 1: conexão recusada na hora, como Redis parado
    limiter = RedisRateLimiter("redis://127.0.0.1:1/0", limit=3, window=60)
    for _ in range(3):
        limiter.check("login:ip:203.0.113.9")
    with pytest.raises(HTTPException) as exc:
        limiter.check("login:ip:203.0.113.9")
    assert exc.value.status_code == 429
    assert limiter.state() == "unreachable"
