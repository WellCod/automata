"""Rotação da chave JWT (ADR-0026): kid na emissão e chave anterior aceita na verificação."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.settings import get_settings


def _pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


_OLD = _pair()
_NEW = _pair()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", _NEW[0])
    monkeypatch.setenv("JWT_PUBLIC_KEY", _NEW[1])
    monkeypatch.delenv("JWT_PREVIOUS_PUBLIC_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _with_previous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_PREVIOUS_PUBLIC_KEY", _OLD[1])
    get_settings.cache_clear()


def _old_token(*, expired: bool = False, kid: bool = True) -> str:
    """Token emitido antes da troca, assinado com a chave velha."""
    from app.auth import key_id

    now = datetime.now(UTC)
    exp = now - timedelta(minutes=1) if expired else now + timedelta(hours=1)
    return jwt.encode(
        {"sub": "u1", "scopes": ["agent_os:admin"], "aud": "automata", "iat": now, "exp": exp},
        _OLD[0],
        algorithm="RS256",
        headers={"kid": key_id(_OLD[1])} if kid else None,
    )


def test_token_novo_leva_kid_da_chave_atual() -> None:
    from app.auth import issue_token, key_id

    token = issue_token("u1", [])
    assert jwt.get_unverified_header(token)["kid"] == key_id(_NEW[1])
    assert key_id(_NEW[1]) != key_id(_OLD[1])
    assert len(key_id(_NEW[1])) == 16


def test_token_da_chave_velha_sem_anterior_e_recusado() -> None:
    from app.auth import decode_token

    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(_old_token())


def test_chave_anterior_aceita_token_velho_com_e_sem_kid(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import decode_token, issue_token

    _with_previous(monkeypatch)
    assert decode_token(_old_token())["sub"] == "u1"
    # emitido antes do kid existir: vale pela tentativa em ordem
    assert decode_token(_old_token(kid=False))["sub"] == "u1"
    assert decode_token(issue_token("u2", []))["sub"] == "u2"


def test_token_velho_vencido_falha_como_vencido(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import decode_token

    _with_previous(monkeypatch)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(_old_token(expired=True))


def test_chaves_de_verificacao_em_ordem(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import verification_keys

    assert verification_keys() == [_NEW[1]]
    _with_previous(monkeypatch)
    assert verification_keys() == [_NEW[1], _OLD[1]]


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    from app.main import create_app

    # sem o `with` o lifespan não roda: só interessa a autenticação, que vem antes do handler
    yield TestClient(
        create_app(auto_provision_dbs=False, enable_auth=True, enable_mcp_server=True),
        raise_server_exceptions=False,
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_mcp_e_agentos_aceitam_a_chave_anterior(monkeypatch: pytest.MonkeyPatch) -> None:
    _with_previous(monkeypatch)
    from app.main import create_app

    app = create_app(auto_provision_dbs=False, enable_auth=True, enable_mcp_server=True)
    with_previous = TestClient(app, raise_server_exceptions=False)
    token = _old_token()
    assert with_previous.get("/mcp", headers=_auth(token)).status_code not in (401, 403)
    assert with_previous.get("/agents", headers=_auth(token)).status_code not in (401, 403)


def test_mcp_e_agentos_recusam_a_chave_velha_sem_anterior(client: TestClient) -> None:
    token = _old_token()
    assert client.get("/mcp", headers=_auth(token)).status_code == 401
    assert client.get("/agents", headers=_auth(token)).status_code == 401
