import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.audit import note
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.evals.gate import draft_verdict
from app.guardrails.instance import effective
from app.guardrails.instance import floor as instance_floor
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import (
    AgentConfigDetail,
    AgentConfigPage,
    AgentConfigResponse,
    AgentConfigVersionDetail,
    AgentConfigVersionSummary,
    ConfigKind,
    ConfigPayload,
    ConfigPayloadStatus,
    CreateConfigInput,
    DraftInput,
    GuardrailSettings,
    RollbackInput,
)
from app.services.config import ConfigService, PlanLimitError

router = APIRouter(
    prefix="/api/v1/configs",
    tags=["configs"],
    dependencies=[Depends(require_scopes(Scope.CONFIGS_READ))],
)
logger = logging.getLogger(__name__)


def _to_version_summary(version: AgentConfigVersion | None) -> AgentConfigVersionSummary | None:
    if version is None:
        return None
    return AgentConfigVersionSummary(
        id=version.id,
        version_number=version.version_number,
        label=version.label,
        status=version.status,
        author=version.author,
        created_at=version.created_at,
    )


def _to_detail(config: AgentConfig, payload: ConfigPayload | None) -> AgentConfigDetail:
    return AgentConfigDetail(
        id=config.id,
        kind=ConfigKind(config.kind),
        name=config.name,
        description=config.description,
        created_at=config.created_at,
        updated_at=config.updated_at,
        current_version=_to_version_summary(config.current_version),
        draft_version=_to_version_summary(config.draft_version),
        payload=payload,
    )


def _to_response(config: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        id=config.id,
        kind=ConfigKind(config.kind),
        name=config.name,
        description=config.description,
        created_at=config.created_at,
        updated_at=config.updated_at,
        current_version=_to_version_summary(config.current_version),
        draft_version=_to_version_summary(config.draft_version),
    )


@router.post(
    "",
    response_model=AgentConfigResponse,
    status_code=201,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_WRITE))],
)
def create_config(body: CreateConfigInput, session: SessionDep) -> AgentConfigResponse:
    """Cria o config vazio, respeitando o limite de plano da instância."""
    config_repo = ConfigRepository(session)
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        config = service.create_config(name=body.name, description=body.description, kind=body.kind)
    except PlanLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    created_config = _to_response(config)
    session.commit()
    return created_config


@router.get("", response_model=AgentConfigPage)
def list_configs(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Busca por nome (substring) ou ID exato"),
    status: ConfigPayloadStatus | None = Query(default=None),  # noqa: B008
    kind: ConfigKind | None = Query(default=None),  # noqa: B008
) -> AgentConfigPage:
    """Lista paginada de configs com busca por nome ou id, status e tipo."""
    config_repo = ConfigRepository(session)
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    items, total = service.list_configs(
        page=page, page_size=page_size, q=q, status=status, kind=kind
    )
    return AgentConfigPage(
        items=[_to_response(config) for config in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{config_id}", response_model=AgentConfigDetail)
def get_config(config_id: UUID, session: SessionDep) -> AgentConfigDetail:
    """Config com a versão vigente, o rascunho e o payload que o editor mostra."""
    config_repo = ConfigRepository(session)
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        config, payload = service.get_detail(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_detail(config, payload)


class EffectiveGuardrails(BaseModel):
    """Guardrails da versão, o piso da instância e o que vale no run (ADR-0034)."""

    own: GuardrailSettings
    floor: GuardrailSettings | None
    effective: GuardrailSettings


@router.get("/{config_id}/guardrails/effective", response_model=EffectiveGuardrails)
def get_effective_guardrails(
    config_id: UUID, session: SessionDep, draft: bool = Query(default=False)
) -> EffectiveGuardrails:
    """Guardrails próprios da versão, o piso da instância e a combinação que vale no run."""
    config_repo = ConfigRepository(session)
    config = config_repo.get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    # sem rascunho, o rascunho é a vigente: o painel pede uma vez só (Fase 43)
    version_id = (
        config.draft_version_id or config.current_version_id if draft else config.current_version_id
    )
    version = config_repo.get_version(version_id) if version_id else None
    if version is None:
        raise HTTPException(status_code=404, detail="Versão não encontrada")
    own = ConfigPayload.model_validate(version.payload).guardrails
    floor_settings = instance_floor()
    return EffectiveGuardrails(
        own=own, floor=floor_settings, effective=effective(floor_settings, own)
    )


@router.get("/{config_id}/teams", response_model=list[AgentConfigResponse])
def list_teams_using(config_id: UUID, session: SessionDep) -> list[AgentConfigResponse]:
    """Times que usam o agente: publicar o agente muda o comportamento deles (ADR-0011)."""
    return [_to_response(team) for team in ConfigRepository(session).teams_using(config_id)]


@router.get("/{config_id}/versions", response_model=list[AgentConfigVersionDetail])
def list_versions(config_id: UUID, session: SessionDep) -> list[AgentConfigVersionDetail]:
    """Todas as versões do config com o payload de cada uma, para o diff."""
    config_repo = ConfigRepository(session)
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        versions = service.list_versions(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        AgentConfigVersionDetail(
            id=version.id,
            version_number=version.version_number,
            label=version.label,
            status=version.status,
            author=version.author,
            created_at=version.created_at,
            payload=ConfigPayload.model_validate(version.payload),
        )
        for version in versions
    ]


@router.post(
    "/{config_id}/publish",
    response_model=AgentConfigVersionSummary,
    status_code=201,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_PUBLISH))],
)
def publish_draft(
    config_id: UUID, session: SessionDep, request: Request
) -> AgentConfigVersionSummary:
    """Publica o rascunho como vigente; com o gate ligado, só com a suíte verde."""
    config_repo = ConfigRepository(session)
    # trava a linha: publicar e mexer no canário ao mesmo tempo não se atropelam (Fase 49)
    config = session.get(AgentConfig, config_id, with_for_update=True)
    previous_version_id = config.current_version_id if config is not None else None
    if config is not None and config.require_passing_evals:
        verdict = draft_verdict(session, config)
        if not verdict.ok:
            # rollback não passa por aqui: voltar para uma versão já publicada segue livre
            raise HTTPException(
                status_code=409, detail=f"Publicação exige a suíte verde: {verdict.reason}"
            )
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        version = service.publish(config_id=config_id, author="panel")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    published_summary = _to_version_summary(version)
    session.commit()
    note(request, current_before=previous_version_id, current_after=version.id)
    # Primeira publicação: o agente passa a responder sem restart
    request.app.state.published_agents.sync()
    logger.info(
        "config published",
        extra={"config_id": str(config_id), "version": version.version_number},
    )
    return published_summary  # type: ignore[return-value]


@router.post(
    "/{config_id}/rollback",
    response_model=AgentConfigVersionSummary,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_PUBLISH))],
)
def rollback(
    config_id: UUID, body: RollbackInput, session: SessionDep, request: Request
) -> AgentConfigVersionSummary:
    """Volta a vigente para uma versão já publicada, sem passar pelo gate da suíte."""
    config_repo = ConfigRepository(session)
    # trava a linha como na publicação, e guarda a vigente de antes para a trilha
    locked_config = session.get(AgentConfig, config_id, with_for_update=True)
    previous_version_id = locked_config.current_version_id if locked_config is not None else None
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        config = service.rollback(config_id=config_id, version_id=body.version_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if config.current_version is None:
        raise HTTPException(status_code=500, detail="Estado inválido após rollback")
    current_summary = _to_version_summary(config.current_version)
    session.commit()
    note(request, current_before=previous_version_id, current_after=body.version_id)
    logger.info(
        "config rolled back",
        extra={"config_id": str(config_id), "version_id": str(body.version_id)},
    )
    return current_summary  # type: ignore[return-value]


@router.put(
    "/{config_id}/draft",
    response_model=AgentConfigVersionSummary,
    status_code=201,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_WRITE))],
)
def save_draft(config_id: UUID, body: DraftInput, session: SessionDep) -> AgentConfigVersionSummary:
    """Grava o rascunho; o payload é validado contra modelo, tools e bases na escrita."""
    config_repo = ConfigRepository(session)
    service = ConfigService(
        config_repo, McpServerRepository(session), KnowledgeBaseRepository(session)
    )
    try:
        version = service.update_draft(
            config_id=config_id,
            name=body.name,
            description=body.description,
            payload=body.payload,
            author="panel",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    draft_summary = AgentConfigVersionSummary(
        id=version.id,
        version_number=version.version_number,
        label=version.label,
        status=version.status,
        author=version.author,
        created_at=version.created_at,
    )
    session.commit()
    return draft_summary
