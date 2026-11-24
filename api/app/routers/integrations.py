"""Tokens para sistemas consumidores chamarem agentes e times via REST ou /mcp."""

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import current_kid, issue_token
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.integrations import MAX_DAYS, integration_scopes
from app.models.caller_budget import CallerBudget
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
    # agentes e times cuja suíte de testes o token pode rodar e consultar
    eval_ids: list[UUID] = Field(default_factory=list)
    # pedidos de exportação e exclusão do próprio titular, integration:<id> (ADR-0036)
    data_subjects: bool = False
    expires_in_days: int = Field(default=30, ge=1, le=MAX_DAYS)


class IntegrationResponse(BaseModel):
    id: UUID
    name: str
    agent_ids: list[UUID]
    team_ids: list[UUID]
    eval_ids: list[UUID]
    data_subjects: bool = False
    created_by: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    # falso enquanto o token depende da chave anterior ou é de antes do kid (ADR-0026)
    on_current_key: bool


class IssuedIntegration(IntegrationResponse):
    # mostrado uma vez só: a API não guarda o token
    token: str
    mcp_url: str | None


def _to_response(integration: IntegrationToken, kid: str | None = None) -> IntegrationResponse:
    """Token sem o segredo; `kid` é a chave JWT atual, para marcar token na anterior."""
    return IntegrationResponse(
        id=integration.id,
        name=integration.name,
        agent_ids=[UUID(i) for i in integration.agent_ids],
        team_ids=[UUID(i) for i in integration.team_ids],
        eval_ids=[UUID(i) for i in integration.eval_ids],
        data_subjects="data_subjects:request" in (integration.scopes or []),
        created_by=integration.created_by,
        created_at=integration.created_at,
        expires_at=integration.expires_at,
        revoked_at=integration.revoked_at,
        on_current_key=integration.signing_kid is not None and integration.signing_kid == kid,
    )


def _check_resources(session: SessionDep, config_ids: list[UUID], kind: ConfigKind) -> None:
    """Recusa id que não existe, de outro tipo ou ainda sem versão publicada."""
    config_repo = ConfigRepository(session)
    for config_id in config_ids:
        config = config_repo.get_config(config_id)
        if config is None or config.kind != kind.value:
            raise HTTPException(status_code=400, detail=f"{kind.value} {config_id} não existe")
        if config.current_version_id is None:
            raise HTTPException(status_code=400, detail=f"'{config.name}' não está publicado")


def _check_suites(session: SessionDep, config_ids: list[UUID]) -> None:
    # a suíte pode rodar no rascunho: não exige versão publicada, só agente ou time
    config_repo = ConfigRepository(session)
    for config_id in config_ids:
        config = config_repo.get_config(config_id)
        if config is None or config.kind == ConfigKind.workflow.value:
            raise HTTPException(status_code=400, detail=f"suíte de {config_id} não existe")


@router.get("", response_model=list[IntegrationResponse])
def list_integrations(session: SessionDep) -> list[IntegrationResponse]:
    rows = session.query(IntegrationToken).order_by(IntegrationToken.created_at.desc()).all()
    kid = current_kid()
    return [_to_response(integration, kid) for integration in rows]


@router.post("", response_model=IssuedIntegration, status_code=201)
def issue(body: IntegrationInput, session: SessionDep, request: Request) -> IssuedIntegration:
    """Emite o token com os scopes dos agentes, times e suítes escolhidos; mostrado uma vez."""
    if not (body.agent_ids or body.team_ids or body.eval_ids or body.data_subjects):
        raise HTTPException(status_code=400, detail="Escolha ao menos um agente ou time")
    _check_resources(session, body.agent_ids, ConfigKind.agent)
    _check_resources(session, body.team_ids, ConfigKind.team)
    _check_suites(session, body.eval_ids)

    token_id = uuid4()
    jti = uuid4().hex
    expires_in = timedelta(days=body.expires_in_days)
    scopes = integration_scopes(body.agent_ids, body.team_ids, body.eval_ids, body.data_subjects)
    integration = IntegrationToken(
        id=token_id,
        name=body.name,
        jti=jti,
        agent_ids=[str(i) for i in body.agent_ids],
        team_ids=[str(i) for i in body.team_ids],
        eval_ids=[str(i) for i in body.eval_ids],
        scopes=scopes,
        created_by=str(getattr(request.state, "user_id", None) or "panel"),
        expires_at=datetime.now(UTC) + expires_in,
        signing_kid=current_kid(),
    )
    session.add(integration)
    default_budget = get_settings().default_integration_budget_usd
    if default_budget > 0:
        # token novo já nasce com teto: vazado, não vira proxy de LLM sem limite (LLM-05)
        session.add(
            CallerBudget(
                subject=f"integration:{token_id}",
                monthly_usd=Decimal(str(default_budget)),
                warn_percent=80,
                hard_stop=True,
                updated_by=integration.created_by,
            )
        )
    session.commit()
    session.refresh(integration)
    token = issue_token(
        f"integration:{token_id}",
        scopes,
        expires_in=int(expires_in.total_seconds()),
        jti=jti,
    )
    public_base_url = get_settings().public_base_url
    logger.info("token de integração emitido", extra={"integration_id": str(token_id)})
    return IssuedIntegration(
        **_to_response(integration, integration.signing_kid).model_dump(),
        token=token,
        mcp_url=f"{public_base_url.rstrip('/')}/mcp" if public_base_url else None,
    )


@router.delete("/{integration_id}", response_model=IntegrationResponse)
def revoke(integration_id: UUID, session: SessionDep, request: Request) -> IntegrationResponse:
    """Revoga o token pelo jti; revogar de novo não muda nada."""
    integration = session.get(IntegrationToken, integration_id)
    if integration is None:
        raise HTTPException(status_code=404, detail="Integração não encontrada")
    if integration.revoked_at is None:
        integration.revoked_at = datetime.now(UTC)
        session.commit()
        session.refresh(integration)
        # este processo recusa na hora; os outros, no próximo refresh do cache
        revoked_tokens = getattr(request.app.state, "revoked_tokens", None)
        if revoked_tokens is not None:
            revoked_tokens.revoke_now(integration.jti)
        logger.info("token de integração revogado", extra={"integration_id": str(integration.id)})
    return _to_response(integration, current_kid())
