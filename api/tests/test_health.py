import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from app.settings import get_settings


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health_db_unreachable() -> None:
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_health_db_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.alerts as alerts

    # outro teste da sessão pode ter rodado o poller neste processo
    monkeypatch.setattr(alerts, "_last_cycle", None)
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        get_settings.cache_clear()

        from app.main import create_app

        client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # banco sem migration ainda: a versão do Alembic fica vazia, sem derrubar o health
    assert body["migration"] is None and body["db"] == "ok"
    assert body["version"] == "dev" and body["redis"] == "off"
    assert body["poller_age_s"] is None
    get_settings.cache_clear()


def test_health_com_versao_migration_e_poller(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    from alembic.config import Config

    import app.alerts as alerts
    from alembic import command

    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        monkeypatch.setenv("DATABASE_URL", pg.get_connection_url().replace("psycopg2", "psycopg"))
        monkeypatch.setenv("AUTOMATA_VERSION", "v9.9.9")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
        monkeypatch.setattr(alerts, "_last_cycle", time.monotonic() - 30)
        body = client.get("/health").json()
        assert body["version"] == "v9.9.9" and body["migration"]
        assert body["status"] == "ok" and 29 <= body["poller_age_s"] <= 40
        # o laço do poller parou: o monitor vê degraded com 200
        monkeypatch.setattr(alerts, "_last_cycle", time.monotonic() - 3600)
        resp = client.get("/health")
        assert resp.status_code == 200 and resp.json()["status"] == "degraded"
    get_settings.cache_clear()
