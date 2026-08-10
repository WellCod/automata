"""Verificação bloqueante: /mcp deve exigir o mesmo JWT que a REST API.

Chama /mcp sem token e com token inválido — ambos devem retornar 401.
Um token válido (com scope adequado) deve passar pelo middleware de auth
e chegar ao handler MCP (qualquer código que não seja 401/403 confirma isso).

Se qualquer assert falhar, enable_mcp_server não sobe em produção.
"""

from collections.abc import Generator

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.settings import get_settings


def _generate_rsa_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_key_pair()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", _PRIVATE_KEY)
    monkeypatch.setenv("JWT_PUBLIC_KEY", _PUBLIC_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mcp_client() -> Generator[TestClient, None, None]:
    from app.main import create_app

    # raise_server_exceptions=False porque o handler MCP do fastmcp lança RuntimeError
    # quando executado sem loop async (contexto de TestClient). Isso é esperado para o
    # terceiro teste — a verificação de auth ocorre antes do handler.
    yield TestClient(
        create_app(auto_provision_dbs=False, enable_auth=True, enable_mcp_server=True),
        raise_server_exceptions=False,
    )


def _token(scopes: list[str] | None = None) -> str:
    from app.auth import issue_token

    return issue_token("u1", scopes or [])


def test_mcp_sem_token_retorna_401(mcp_client: TestClient) -> None:
    """/mcp sem credencial deve ser bloqueado pelo middleware de auth."""
    response = mcp_client.get("/mcp")
    assert response.status_code == 401, (
        f"/mcp retornou {response.status_code} sem token — endpoint exposto sem autenticação"
    )


def test_mcp_com_token_invalido_retorna_401(mcp_client: TestClient) -> None:
    response = mcp_client.get("/mcp", headers={"Authorization": "Bearer token-invalido"})
    assert response.status_code == 401


def test_mcp_com_token_valido_passa_pelo_middleware(mcp_client: TestClient) -> None:
    """Token válido deve ultrapassar o middleware de auth (código != 401/403)."""
    token = _token(scopes=["agent_os:admin"])
    response = mcp_client.get("/mcp", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code not in (401, 403), (
        f"/mcp retornou {response.status_code} com token válido"
        " — middleware bloqueando indevidamente"
    )
