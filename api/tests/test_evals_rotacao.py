"""Evals da rotação de chaves (ADR-0026).

Sem banco e sem rede: rodam em todo PR. Errar aqui é derrubar as integrações na
troca da chave, aceitar token que não devia ou esquecer um segredo na chave velha.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

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


_OLD, _NEW, _STRANGER = _pair(), _pair(), _pair()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", _NEW[0])
    monkeypatch.setenv("JWT_PUBLIC_KEY", _NEW[1])
    monkeypatch.setenv("JWT_PREVIOUS_PUBLIC_KEY", _OLD[1])
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sign(
    private: str,
    *,
    kid: str | None = None,
    aud: str = "automata",
    exp_minutes: int = 60,
    alg: str = "RS256",
) -> str:
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": "u1",
        "scopes": [],
        "aud": aud,
        "iat": now,
        "exp": now + timedelta(minutes=exp_minutes),
    }
    return jwt.encode(claims, private, algorithm=alg, headers={"kid": kid} if kid else None)


def _kid(pair: tuple[str, str]) -> str:
    from app.auth import key_id

    return key_id(pair[1])


@pytest.mark.parametrize(
    ("case", "accepted"),
    [
        ("atual com kid", True),
        ("anterior com kid", True),
        ("anterior sem kid", True),
        ("anterior com o kid da atual", True),
        ("chave desconhecida", False),
        ("chave desconhecida com o kid da atual", False),
        ("anterior vencido", False),
        ("anterior de outra audiência", False),
        ("HS256 com a chave pública como segredo", False),
    ],
)
def test_quem_entra_durante_a_troca(case: str, accepted: bool) -> None:
    from app.auth import decode_token

    tokens = {
        "atual com kid": lambda: _sign(_NEW[0], kid=_kid(_NEW)),
        "anterior com kid": lambda: _sign(_OLD[0], kid=_kid(_OLD)),
        "anterior sem kid": lambda: _sign(_OLD[0]),
        # kid é dica de ordem, não prova: a assinatura decide
        "anterior com o kid da atual": lambda: _sign(_OLD[0], kid=_kid(_NEW)),
        "chave desconhecida": lambda: _sign(_STRANGER[0], kid=_kid(_STRANGER)),
        "chave desconhecida com o kid da atual": lambda: _sign(_STRANGER[0], kid=_kid(_NEW)),
        "anterior vencido": lambda: _sign(_OLD[0], kid=_kid(_OLD), exp_minutes=-1),
        "anterior de outra audiência": lambda: _sign(_OLD[0], kid=_kid(_OLD), aud="outra"),
        # confusão de algoritmo: a pública é conhecida, e HS256 com ela não pode passar
        "HS256 com a chave pública como segredo": lambda: _hs256_with_public_key(),
    }
    token = tokens[case]()
    if accepted:
        assert decode_token(token)["sub"] == "u1"
    else:
        with pytest.raises(jwt.InvalidTokenError):
            decode_token(token)


def _hs256_with_public_key() -> str:
    # o PyJWT recusa assinar HMAC com PEM; monta o token à mão como faria um atacante
    import base64
    import hashlib
    import hmac
    import json

    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    exp = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    payload = b64(json.dumps({"sub": "u1", "aud": "automata", "exp": exp}).encode())
    signature = hmac.new(_OLD[1].encode(), f"{header}.{payload}".encode(), hashlib.sha256)
    return f"{header}.{payload}.{b64(signature.digest())}"


def test_vencido_falha_como_vencido_e_nao_como_assinatura() -> None:
    from app.auth import decode_token

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(_sign(_OLD[0], kid=_kid(_OLD), exp_minutes=-1))


def test_sem_a_anterior_o_token_velho_cai(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.auth import decode_token

    monkeypatch.delenv("JWT_PREVIOUS_PUBLIC_KEY")
    get_settings.cache_clear()
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(_sign(_OLD[0], kid=_kid(_OLD)))
    assert decode_token(_sign(_NEW[0], kid=_kid(_NEW)))["sub"] == "u1"


def test_emissao_usa_sempre_a_atual() -> None:
    from app.auth import issue_token

    token = issue_token("u1", [])
    assert jwt.get_unverified_header(token)["kid"] == _kid(_NEW)
    jwt.decode(token, _NEW[1], algorithms=["RS256"], audience="automata")


@pytest.mark.parametrize(
    ("stored_with", "current", "previous", "readable"),
    [
        ("nova", "nova", None, True),
        ("velha", "nova", "velha", True),
        ("velha", "nova", None, False),
        ("outra", "nova", "velha", False),
    ],
)
def test_quem_le_os_segredos(
    monkeypatch: pytest.MonkeyPatch,
    stored_with: str,
    current: str,
    previous: str | None,
    readable: bool,
) -> None:
    from app.secrets import SecretsKeyMissing, decrypt_json

    keys = {name: Fernet.generate_key() for name in ("nova", "velha", "outra")}
    token = Fernet(keys[stored_with]).encrypt(b'{"token": "x"}').decode()
    monkeypatch.setenv("MCP_SECRETS_KEY", keys[current].decode())
    if previous:
        monkeypatch.setenv("MCP_SECRETS_PREVIOUS_KEY", keys[previous].decode())
    else:
        monkeypatch.delenv("MCP_SECRETS_PREVIOUS_KEY", raising=False)
    get_settings.cache_clear()
    if readable:
        assert decrypt_json(token) == {"token": "x"}
    else:
        with pytest.raises(SecretsKeyMissing):
            decrypt_json(token)


def test_toda_coluna_cifrada_entra_no_comando_de_recifrar() -> None:
    import app.models  # noqa: F401  registra todos os modelos no metadata
    from app.models.config import Base
    from app.rotate_secrets import ENCRYPTED

    encrypted = {
        (table.name, column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.name.endswith("_encrypted")
    }
    covered = {(table, column.key) for table, column in ENCRYPTED.items()}
    assert encrypted == covered, "coluna cifrada nova precisa entrar em ENCRYPTED"
