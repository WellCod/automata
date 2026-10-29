import hashlib
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization

from app.settings import get_settings

_ALGORITHM = "RS256"
_DEFAULT_EXPIRY = 3600  # 1 hora
_AUDIENCE = "automata"


@lru_cache(maxsize=8)
def key_id(public_key_pem: str) -> str:
    """16 primeiros hexadecimais do SHA-256 da chave pública em DER (ADR-0026)."""
    key = serialization.load_pem_public_key(public_key_pem.encode())
    der = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return hashlib.sha256(der).hexdigest()[:16]


def safe_kid(public_key_pem: str) -> str | None:
    try:
        return key_id(public_key_pem)
    except ValueError:
        return None


def current_kid() -> str | None:
    """kid da chave atual; None quando a chave configurada não é PEM (testes sem JWT)."""
    return safe_kid(get_settings().jwt_public_key)


def verification_keys() -> list[str]:
    """Chave atual primeiro; a anterior só existe durante a rotação."""
    settings = get_settings()
    keys = [settings.jwt_public_key]
    if settings.jwt_previous_public_key:
        keys.append(settings.jwt_previous_public_key)
    return keys


def decode_token(token: str, *, audience: str = _AUDIENCE) -> dict[str, Any]:
    """Verifica com a chave do `kid` primeiro e depois com as outras.

    Só assinatura inválida passa para a próxima chave: token vencido ou de outra
    audiência falha na chave certa e não deve virar "assinatura inválida".
    """
    keys = verification_keys()
    kid = jwt.get_unverified_header(token).get("kid")
    if kid:
        keys.sort(key=lambda k: safe_kid(k) != kid)
    last: jwt.InvalidTokenError = jwt.InvalidSignatureError("nenhuma chave verificou o token")
    for key in keys:
        try:
            payload: dict[str, Any] = jwt.decode(
                token, key, algorithms=[_ALGORITHM], audience=audience
            )
            return payload
        except jwt.InvalidSignatureError as exc:
            last = exc
    raise last


def issue_token(
    user_id: str,
    scopes: list[str],
    *,
    audience: str = _AUDIENCE,
    expires_in: int = _DEFAULT_EXPIRY,
    jti: str | None = None,
) -> str:
    """Emite JWT RS256 assinado com a chave privada da instância.

    A chave privada nunca deve sair do servidor — chamado apenas pelo BFF do
    painel (Next.js Route Handler) e pelos testes de integração. Nunca pelo
    browser diretamente (ADR-0005).
    """
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": user_id,
        "scopes": scopes,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
        # identifica o token para revogação (logout e tokens de integração)
        "jti": jti or uuid4().hex,
    }
    return jwt.encode(
        payload,
        settings.jwt_private_key,
        algorithm=_ALGORITHM,
        headers={"kid": key_id(settings.jwt_public_key)},
    )
