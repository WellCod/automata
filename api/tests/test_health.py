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


def test_health_db_ok() -> None:
    with PostgresContainer("postgres:17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        get_settings.cache_clear()

        from app.main import create_app

        client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    get_settings.cache_clear()
