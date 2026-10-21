"""Fila durável dos runs em background (ADR-0020): o run passa pela fila e pelo factory."""

import os
import time
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.main import QUEUE_MAX_ATTEMPTS, QUEUE_TIMEOUT_S, background_queue
from app.settings import Settings, get_settings


def _settings(**over: Any) -> Settings:
    base = {"database_url": "postgresql://x", "jwt_private_key": "x", "jwt_public_key": "x"}
    return Settings(**{**base, **over})  # type: ignore[arg-type]


def test_uma_tentativa_e_quinze_minutos() -> None:
    queue = background_queue(_settings())
    assert queue is not None and queue.durable
    # tool com efeito pode ter rodado antes da queda: nunca roda de novo sozinho
    assert (queue.max_attempts, queue.timeout_seconds) == (QUEUE_MAX_ATTEMPTS, QUEUE_TIMEOUT_S)
    assert (QUEUE_MAX_ATTEMPTS, QUEUE_TIMEOUT_S) == (1, 900)
    assert queue.redis is None


def test_redis_quando_existe_e_interruptor() -> None:
    with_redis = background_queue(_settings(redis_url="redis://redis:6379/0"))
    assert with_redis is not None and with_redis.redis == "redis://redis:6379/0"
    assert background_queue(_settings(background_queue_durable=False)) is None


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {"DATABASE_URL": url, "DEMO_REPLAY": "true"}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        # o `with` roda o lifespan: é nele que o worker da fila sobe
        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def test_run_em_background_passa_pela_fila_e_pelo_factory(client: TestClient) -> None:
    from app.db import get_engine

    body = {"name": "na fila", "description": "Use para na fila"}
    agent = client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"]
    client.put(
        f"/api/v1/configs/{agent}/draft", json={**body, "payload": {"model_id": "claude-haiku-4-5"}}
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()

    accepted = client.post(
        f"/agents/{agent}/runs",
        data={"message": "oi", "stream": "false", "background": "true", "session_id": "fila-1"},
    )
    assert accepted.status_code == 202, accepted.text
    run_id = accepted.json()["run_id"]
    assert accepted.json()["status"] == "PENDING"

    status = None
    for _ in range(40):
        resp = client.get(f"/agents/{agent}/runs/{run_id}", params={"session_id": "fila-1"})
        status = resp.json().get("status") if resp.status_code == 200 else None
        if status in ("COMPLETED", "ERROR"):
            break
        time.sleep(0.25)
    assert status == "COMPLETED"

    # o aceite foi uma linha commitada na fila (agno_jobs), não só uma task em memória
    with get_engine().connect() as conn:
        jobs = conn.execute(text("SELECT count(*) FROM ai.agno_jobs")).scalar_one()
    assert jobs >= 1
    runs = client.get(f"/api/v1/configs/{agent}/runs").json()
    assert [r["status"] for r in runs["items"]] == ["success"]
