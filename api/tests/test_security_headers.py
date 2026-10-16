"""HSTS atrás de proxy TLS e docs do OpenAPI só em desenvolvimento."""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.settings import get_settings

_HSTS = "Strict-Transport-Security"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8")
    monkeypatch.delenv("APP_ENV", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _app() -> FastAPI:
    from app.main import create_app

    return create_app(auto_provision_dbs=False, enable_auth=False, enable_mcp_server=False)


def _client(peer: str, base_url: str = "http://testserver") -> TestClient:
    return TestClient(_app(), base_url=base_url, client=(peer, 50000))


def test_hsts_com_https_direto() -> None:
    response = _client("203.0.113.9", "https://testserver").get("/health")
    assert response.headers[_HSTS].startswith("max-age=")


def test_hsts_com_forwarded_proto_de_proxy_confiavel() -> None:
    response = _client("10.0.0.2").get("/health", headers={"X-Forwarded-Proto": "https"})
    assert response.headers[_HSTS].startswith("max-age=")


def test_sem_hsts_com_forwarded_proto_de_peer_nao_confiavel() -> None:
    response = _client("203.0.113.9").get("/health", headers={"X-Forwarded-Proto": "https"})
    assert _HSTS not in response.headers


def test_sem_hsts_em_http_atras_de_proxy_confiavel() -> None:
    response = _client("10.0.0.2").get("/health", headers={"X-Forwarded-Proto": "http"})
    assert _HSTS not in response.headers


def test_sem_hsts_sem_proxies_configurados(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    get_settings.cache_clear()
    response = _client("10.0.0.2").get("/health", headers={"X-Forwarded-Proto": "https"})
    assert _HSTS not in response.headers


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_desligados_fora_de_dev(path: str) -> None:
    assert _client("203.0.113.9").get(path).status_code == 404


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_ligados_em_dev(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    get_settings.cache_clear()
    assert _client("203.0.113.9").get(path).status_code == 200
