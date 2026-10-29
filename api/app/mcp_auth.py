"""TokenVerifier para o endpoint /mcp que reutiliza o mesmo RS256 JWT da API."""

import jwt
from fastmcp.server.auth import AccessToken, TokenVerifier

from app.auth import decode_token


class JWTMCPAuth(TokenVerifier):
    """Verifica Bearer tokens RS256 no endpoint /mcp.

    Reutiliza as mesmas chaves públicas e audiência da API HTTP, garantindo que
    /mcp exige o mesmo JWT que as demais rotas protegidas.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            payload = decode_token(token)
        except jwt.InvalidTokenError:
            return None

        scopes: list[str] = payload.get("scopes", [])
        return AccessToken(
            token=token,
            client_id=payload.get("sub", ""),
            scopes=scopes,
            expires_at=payload.get("exp"),
            subject=payload.get("sub"),
        )
