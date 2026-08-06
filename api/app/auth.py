from datetime import UTC, datetime, timedelta

import jwt

from app.settings import get_settings

_ALGORITHM = "RS256"
_DEFAULT_EXPIRY = 3600  # 1 hora


def issue_token(
    user_id: str,
    scopes: list[str],
    *,
    audience: str = "automata",
    expires_in: int = _DEFAULT_EXPIRY,
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
    }
    return jwt.encode(payload, settings.jwt_private_key, algorithm=_ALGORITHM)
