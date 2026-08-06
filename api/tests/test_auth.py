"""Testes de autorização JWT RS256.

Usa par de chaves RSA gerado em memória — nunca usa chaves de produção.
"""

from collections.abc import Generator

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.settings import get_settings


def _generate_rsa_key_pair() -> tuple[str, str]:
    """Gera par RSA 2048 e retorna (private_pem, public_pem) como strings."""
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


@pytest.fixture
def client_with_auth(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", _PRIVATE_KEY)
    monkeypatch.setenv("JWT_PUBLIC_KEY", _PUBLIC_KEY)
    get_settings.cache_clear()

    from app.main import create_app

    yield TestClient(create_app(auto_provision_dbs=False, enable_auth=True))
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", _PRIVATE_KEY)
    monkeypatch.setenv("JWT_PUBLIC_KEY", _PUBLIC_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _token(user_id: str = "u1", scopes: list[str] | None = None) -> str:
    from app.auth import issue_token

    return issue_token(user_id, scopes or [])


# --- emissão de token ---


def test_issue_token_retorna_string() -> None:
    token = _token("u1", ["agents:read"])
    assert isinstance(token, str)
    assert len(token) > 0


def test_issue_token_decodificavel_com_chave_publica() -> None:
    import jwt

    token = _token("u1", ["agents:read"])
    payload = jwt.decode(
        token,
        _PUBLIC_KEY,
        algorithms=["RS256"],
        audience="automata",
        options={"verify_exp": False},
    )
    assert payload["sub"] == "u1"
    assert "agents:read" in payload["scopes"]


def test_issue_token_audience_padrao_e_automata() -> None:
    import jwt

    token = _token("u1")
    payload = jwt.decode(
        token,
        _PUBLIC_KEY,
        algorithms=["RS256"],
        audience="automata",
        options={"verify_exp": False},
    )
    assert payload["aud"] == "automata"


def test_issue_token_audience_customizavel() -> None:
    import jwt

    from app.auth import issue_token

    token = issue_token("u1", [], audience="outro-sistema")
    payload = jwt.decode(
        token,
        _PUBLIC_KEY,
        algorithms=["RS256"],
        audience="outro-sistema",
        options={"verify_exp": False},
    )
    assert payload["aud"] == "outro-sistema"


# --- autorização pelo AgentOS ---


def test_health_acessivel_sem_token(client_with_auth: TestClient) -> None:
    response = client_with_auth.get("/health")
    assert response.status_code == 200


def test_rota_protegida_sem_token_retorna_401(client_with_auth: TestClient) -> None:
    response = client_with_auth.get("/agents")
    assert response.status_code == 401


def test_rota_protegida_com_token_invalido_retorna_401(client_with_auth: TestClient) -> None:
    response = client_with_auth.get("/agents", headers={"Authorization": "Bearer token-invalido"})
    assert response.status_code == 401


def test_rota_protegida_sem_scope_retorna_403(client_with_auth: TestClient) -> None:
    token = _token("u1", scopes=[])
    response = client_with_auth.get("/agents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_rota_protegida_com_scope_correto_retorna_200(client_with_auth: TestClient) -> None:
    token = _token("u1", scopes=["agents:read"])
    response = client_with_auth.get("/agents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_admin_scope_acessa_qualquer_rota(client_with_auth: TestClient) -> None:
    token = _token("admin", scopes=["agent_os:admin"])
    response = client_with_auth.get("/agents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_rota_propria_acessivel_com_token_sem_scope(client_with_auth: TestClient) -> None:
    token = _token("u1", scopes=[])
    response = client_with_auth.get(
        "/api/v1/models/capabilities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
