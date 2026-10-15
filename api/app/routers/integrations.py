"""Tokens para sistemas consumidores chamarem agentes e times via REST ou /mcp."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import issue_token
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.integrations import MAX_DAYS, integration_scopes
from app.models.integration import IntegrationToken
from app.repositories.config import ConfigRepository
from app.schemas.config import ConfigKind
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/integrations",
    tags=["integrations"],
    # emitir token é dar acesso a terceiros: só owner
    dependencies=[Depends(require_scopes(Scope.INTEGRATIONS_WRITE))],
)
logger = logging.getLogger(__name__)


class IntegrationInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    agent_ids: list[UUID] = Field(default_factory=list)
    team_ids: list[UUID] = Field(default_factory=list)
    expires_in_days: int = Field(default=30, ge=1, le=MAX_DAYS)


class IntegrationResponse(BaseModel):
    id: UUID
    name: str
    agent_ids: list[UUID]
    team_ids: list[UUID]
    created_by: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class IssuedIntegration(IntegrationResponse):
    # mostrado uma vez só: a API não guarda o token
    token: str
    mcp_url: str | None


def _to_response(t: IntegrationToken) -> IntegrationResponse:
    return IntegrationResponse(
        id=t.id,
        name=t.name,
        agent_ids=[UUID(i) for i in t.agent_ids],
        team_ids=[UUID(i) for i in t.team_ids],
        created_by=t.created_by,
        created_at=t.created_at,
        expires_at=t.expires_at,
        revoked_at=t.revoked_at,
    )


def _check_resources(session: SessionDep, ids: list[UUID], kind: ConfigKind) -> None:
    repo = ConfigRepository(session)
    for config_id in ids:
        config = repo.get_config(config_id)
        if config is None or config.kind != kind.value:
            raise HTTPException(status_code=400, detail=f"{kind.value} {config_id} não existe")
        if config.current_version_id is None:
            raise HTTPException(status_code=400, detail=f"'{config.name}' não está publicado")


@router.get("", response_model=list[IntegrationResponse])
def list_integrations(session: SessionDep) -> list[IntegrationResponse]:
    rows = session.query(IntegrationToken).order_by(IntegrationToken.created_at.desc()).all()
    return [_to_response(t) for t in rows]


@router.post("", response_model=IssuedIntegration, status_code=201)
def issue(body: IntegrationInput, session: SessionDep, request: Request) -> IssuedIntegration:
    if not body.agent_ids and not body.team_ids:
        raise HTTPException(status_code=400, detail="Escolha ao menos um agente ou time")
    _check_resources(session, body.agent_ids, ConfigKind.agent)
    _check_resources(session, body.team_ids, ConfigKind.team)

    token_id = uuid4()
    jti = uuid4().hex
    expires_in = timedelta(days=body.expires_in_days)
    scopes = integration_scopes(body.agent_ids, body.team_ids)
    row = IntegrationToken(
        id=token_id,
        name=body.name,
        jti=jti,
        agent_ids=[str(i) for i in body.agent_ids],
        team_ids=[str(i) for i in body.team_ids],
        scopes=scopes,
        created_by=str(getattr(request.state, "user_id", None) or "panel"),
        expires_at=datetime.now(UTC) + expires_in,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    token = issue_token(
        f"integration:{token_id}",
        scopes,
        expires_in=int(expires_in.total_seconds()),
        jti=jti,
    )
    base = get_settings().public_base_url
    logger.info("token de integração emitido", extra={"integration_id": str(token_id)})
    return IssuedIntegration(
        **_to_response(row).model_dump(),
        token=token,
        mcp_url=f"{base.rstrip('/')}/mcp" if base else None,
    )


@router.delete("/{integration_id}", response_model=IntegrationResponse)
def revoke(integration_id: UUID, session: SessionDep, request: Request) -> IntegrationResponse:
    row = session.get(IntegrationToken, integration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.commit()
        session.refresh(row)
        # este processo recusa na hora; os outros, no próximo refresh do cache
        revoked = getattr(request.app.state, "revoked_tokens", None)
        if revoked is not None:
            revoked.revoke_now(row.jti)
        logger.info("token de integração revogado", extra={"integration_id": str(row.id)})
    return _to_response(row)
