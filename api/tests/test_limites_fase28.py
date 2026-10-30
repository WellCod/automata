"""Achados baixos da auditoria da Fase 28: login, busca na base, S3 e log."""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.rate_limit import MemoryRateLimiter
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def login_app(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Só a rota de login, com o IP vindo de um header e a senha sempre errada."""
    import app.routers.auth as auth

    monkeypatch.setattr(auth, "get_client_ip", lambda request: request.headers["x-test-ip"])

    class _Wrong:
        def __init__(self, *args: Any) -> None:
            pass

        def authenticate(self, email: str, password: str) -> None:
            raise ValueError("credenciais")

    monkeypatch.setattr(auth, "UserService", _Wrong)
    monkeypatch.setattr(auth, "UserRepository", lambda session: None)
    app = FastAPI()
    app.state.rate_limiter = MemoryRateLimiter(limit=5, window=60)
    app.include_router(auth.router)
    from app.db import get_session

    def _session() -> Generator[Any, None, None]:
        yield SimpleNamespace(commit=lambda: None)

    app.dependency_overrides[get_session] = _session
    return TestClient(app)


def _try(client: TestClient, ip: str, email: str = "owner@empresa.com") -> int:
    body = {"email": email, "password": "Errada123456"}
    return client.post("/api/v1/auth/login", json=body, headers={"x-test-ip": ip}).status_code


def test_tentativas_de_um_ip_nao_travam_o_login_dos_outros(login_app: TestClient) -> None:
    assert [_try(login_app, "203.0.113.9") for _ in range(5)] == [401] * 5
    assert _try(login_app, "203.0.113.9") == 429
    # o dono da conta, de outro IP, ainda consegue tentar
    assert _try(login_app, "198.51.100.7") == 401


def test_forca_bruta_distribuida_para_no_limite_por_email(login_app: TestClient) -> None:
    codes = [_try(login_app, f"203.0.113.{i}") for i in range(1, 32)]
    assert codes[:30] == [401] * 30
    assert codes[30] == 429


def test_log_do_login_nao_grava_o_email(
    login_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.routers.auth as auth

    lines: list[str] = []

    class _Logger:
        def _keep(self, msg: str, *args: Any, extra: dict[str, Any] | None = None) -> None:
            lines.append(f"{msg} {extra}")

        info = warning = _keep

    monkeypatch.setattr(auth, "logger", _Logger())
    _try(login_app, "203.0.113.9", "fulano@empresa.com")
    text = " ".join(lines)
    assert "fulano@empresa.com" not in text
    assert "email_ref" in text


def test_busca_na_base_tem_limite_por_usuario() -> None:
    from app.routers.knowledge_bases import _SEARCH_LIMIT, _limit_search

    limiter = MemoryRateLimiter(limit=5, window=60)
    request: Any = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(rate_limiter=limiter)),
        state=SimpleNamespace(user_id="ana"),
    )
    for _ in range(_SEARCH_LIMIT):
        _limit_search(request)
    with pytest.raises(HTTPException) as exc:
        _limit_search(request)
    assert exc.value.status_code == 429
    request.state.user_id = "bruno"
    _limit_search(request)


def test_s3_com_endpoint_proprio_exige_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.knowledge.sources import S3Source, SourceError
    from app.schemas.knowledge_connector import S3Settings

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "minio.interno")
    get_settings.cache_clear()
    settings = S3Settings(bucket="docs", endpoint_url="http://minio.interno:9000")
    with pytest.raises(SourceError, match="access key"):
        S3Source(settings, {})._client()
    client = S3Source(settings, {"access_key_id": "k", "secret_access_key": "s"})._client()
    assert client.meta.endpoint_url == "http://minio.interno:9000"
