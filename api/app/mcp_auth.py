"""TokenVerifier para o endpoint /mcp que reutiliza o mesmo RS256 JWT da API."""

import jwt
from fastmcp.server.auth import AccessToken, TokenVerifier

from app.settings import get_settings


class JWTMCPAuth(TokenVerifier):
    """Verifica Bearer tokens RS256 no endpoint /mcp.

    Reutiliza a mesma chave pública e audiência da API HTTP, garantindo que
    /mcp exige o mesmo JWT que as demais rotas protegidas.
    """

    async def verify_token(self, token: str) -> AccessToken | None:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.jwt_public_key,
                algorithms=["RS256"],
                audience="automata",
            )
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
