"""Tokens de integração e revogação por jti (ADR-0009), também usada no logout.

O middleware do AgentOS só valida assinatura e expiração; não conhece
revogação. RevokedTokens consulta os jti revogados ainda não expirados,
com cache curto, e o middleware recusa o token antes de chegar ao Agno.
"""

import logging
import math
import threading
from datetime import UTC, datetime
from time import monotonic
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.db import get_engine
from app.models.integration import IntegrationToken
from app.models.revoked_token import RevokedToken
from app.models.user import User

logger = logging.getLogger(__name__)

MAX_DAYS = 90


def integration_scopes(
    agent_ids: list[UUID], team_ids: list[UUID], eval_ids: list[UUID] | None = None
) -> list[str]:
    """Ler e executar só os recursos liberados; nada de sessões de outros nem config.

    Na suíte, rodar e ler o resultado; criar ou editar caso e mexer no gate, não.
    """
    scopes: list[str] = []
    for agent_id in agent_ids:
        scopes += [f"agents:{agent_id}:read", f"agents:{agent_id}:run"]
    for team_id in team_ids:
        scopes += [f"teams:{team_id}:read", f"teams:{team_id}:run"]
    for config_id in eval_ids or []:
        scopes += [f"evals:{config_id}:read", f"evals:{config_id}:run"]
    return scopes


def _load_cutoffs() -> dict[str, float]:
    """sub do usuário -> instante antes do qual os tokens dele não valem mais."""
    with Session(get_engine()) as session:
        rows = session.execute(
            select(User.id, User.tokens_valid_after).where(User.tokens_valid_after.is_not(None))
        )
        return {str(r.id): r.tokens_valid_after.timestamp() for r in rows}


def _load_revoked() -> set[str]:
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        integrations = select(IntegrationToken.jti).where(
            IntegrationToken.revoked_at.is_not(None), IntegrationToken.expires_at > now
        )
        sessions = select(RevokedToken.jti).where(RevokedToken.expires_at > now)
        return set(session.scalars(integrations)) | set(session.scalars(sessions))


class RevokedTokens:
    def __init__(self, ttl_seconds: float = 30.0) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._revoked: set[str] = set()
        self._cutoffs: dict[str, float] = {}
        self._loaded_at: float | None = None

    def is_revoked(self, jti: str | None, sub: str | None = None, iat: float | None = None) -> bool:
        with self._lock:
            stale = self._loaded_at is None or monotonic() - self._loaded_at >= self._ttl
        if stale:
            self.refresh()
        if jti is not None and jti in self._revoked:
            return True
        cutoff = self._cutoffs.get(sub) if sub else None
        # iat é em segundos inteiros: o corte vale até o fim do segundo da mudança, para
        # nenhum token anterior escapar (login nesse mesmo segundo precisa ser refeito)
        return cutoff is not None and iat is not None and iat < math.ceil(cutoff)

    def refresh(self) -> None:
        try:
            revoked = _load_revoked()
            cutoffs = _load_cutoffs()
        except Exception as exc:
            # Mantém a última lista e só tenta de novo após o TTL: sem isso, banco
            # fora do ar somaria um timeout de conexão a cada request com token
            logger.warning("falha ao carregar tokens revogados", extra={"error": str(exc)})
            with self._lock:
                self._loaded_at = monotonic()
            return
        with self._lock:
            self._revoked = revoked
            self._cutoffs = cutoffs
            self._loaded_at = monotonic()

    def revoke_now(self, jti: str) -> None:
        with self._lock:
            self._revoked.add(jti)

    def cut_now(self, sub: str, at: float) -> None:
        with self._lock:
            self._cutoffs[sub] = at


class RevocationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, revoked: RevokedTokens) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._revoked = revoked

    async def dispatch(self, request: Request, call_next: object) -> Response:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            try:
                # assinatura é checada pelo Agno; aqui só interessa o jti
                claims = jwt.decode(auth[7:], options={"verify_signature": False})
            except jwt.InvalidTokenError:
                claims = {}
            jti = claims.get("jti")
            sub = claims.get("sub")
            iat = claims.get("iat")
            revoked = await run_in_threadpool(
                self._revoked.is_revoked,
                jti if isinstance(jti, str) else None,
                sub if isinstance(sub, str) else None,
                float(iat) if isinstance(iat, int | float) else None,
            )
            if revoked:
                return JSONResponse({"detail": "Token revogado"}, status_code=401)
        response: Response = await call_next(request)  # type: ignore[operator]
        return response
