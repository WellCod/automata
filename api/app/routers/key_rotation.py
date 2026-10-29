"""Estado da rotação das chaves da instância (ADR-0026), só para o owner.

A rotação termina quando nenhum token de integração ativo depende da chave JWT
anterior e nenhum segredo depende da chave anterior dos segredos. Aí as
variáveis `*_PREVIOUS_*` podem sair do ambiente.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth import current_kid, safe_kid
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.integration import IntegrationToken
from app.rotate_secrets import pending
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/key-rotation",
    tags=["key-rotation"],
    dependencies=[Depends(require_scopes(Scope.KEYS_ADMIN))],
)


class JwtRotation(BaseModel):
    current_kid: str | None
    previous_kid: str | None
    # tokens de integração ativos assinados com outra chave que não a atual
    tokens_on_previous: int
    # tokens de integração ativos emitidos antes do kid existir
    tokens_without_kid: int


class SecretsRotation(BaseModel):
    configured: bool
    previous_configured: bool
    # por tabela, quantos segredos a chave atual ainda não abre
    pending: dict[str, int]


class KeyRotationStatus(BaseModel):
    jwt: JwtRotation
    secrets: SecretsRotation
    # nada depende das chaves anteriores: as variáveis *_PREVIOUS_* podem sair
    done: bool


@router.get("", response_model=KeyRotationStatus)
def rotation_status(session: SessionDep) -> KeyRotationStatus:
    settings = get_settings()
    kid = current_kid()
    active = (IntegrationToken.revoked_at.is_(None)) & (
        IntegrationToken.expires_at > datetime.now(UTC)
    )
    active_count = select(func.count()).select_from(IntegrationToken).where(active)
    other_key = active_count.where(IntegrationToken.signing_kid.is_not(None))
    if kid is not None:
        other_key = other_key.where(IntegrationToken.signing_kid != kid)
    on_previous = session.scalar(other_key)
    without_kid = session.scalar(active_count.where(IntegrationToken.signing_kid.is_(None)))
    jwt = JwtRotation(
        current_kid=kid,
        previous_kid=(
            safe_kid(settings.jwt_previous_public_key) if settings.jwt_previous_public_key else None
        ),
        tokens_on_previous=on_previous or 0,
        tokens_without_kid=without_kid or 0,
    )
    configured = bool(settings.mcp_secrets_key)
    secrets = SecretsRotation(
        configured=configured,
        previous_configured=bool(settings.mcp_secrets_previous_key),
        pending=pending(session) if configured else {},
    )
    done = (
        jwt.tokens_on_previous == 0
        and jwt.tokens_without_kid == 0
        and not any(secrets.pending.values())
    )
    return KeyRotationStatus(jwt=jwt, secrets=secrets, done=done)
