from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.settings import get_settings


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_health() -> None:
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
