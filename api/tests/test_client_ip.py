"""IP do cliente para rate limit: X-Forwarded-For só vale vindo de proxy confiável."""

from collections.abc import Generator

import pytest
from starlette.requests import Request

from app.proxy import get_client_ip
from app.settings import get_settings


def _request(peer: str, xff: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.0/8, 172.18.0.5")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_ignora_header_de_cliente_nao_confiavel() -> None:
    assert get_client_ip(_request("203.0.113.9", "1.2.3.4")) == "203.0.113.9"


def test_usa_ultimo_hop_nao_confiavel() -> None:
    # cliente forjou 1.2.3.4; o proxy confiável anexou o IP real
    req = _request("172.18.0.5", "1.2.3.4, 198.51.100.7, 10.0.0.2")
    assert get_client_ip(req) == "198.51.100.7"


def test_proxy_confiavel_sem_header_usa_ip_da_conexao() -> None:
    assert get_client_ip(_request("10.1.2.3")) == "10.1.2.3"


def test_sem_proxies_configurados_ignora_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRUSTED_PROXIES", "")
    get_settings.cache_clear()
    assert get_client_ip(_request("10.0.0.2", "1.2.3.4")) == "10.0.0.2"


def test_hop_invalido_nao_e_confiavel() -> None:
    assert get_client_ip(_request("10.0.0.2", "lixo")) == "lixo"
