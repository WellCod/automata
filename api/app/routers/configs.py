from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionDep
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.schemas.config import (
    AgentConfigDetail,
    AgentConfigPage,
    AgentConfigResponse,
    AgentConfigVersionDetail,
    AgentConfigVersionSummary,
    ConfigPayload,
    ConfigPayloadStatus,
    CreateConfigInput,
    DraftInput,
    RollbackInput,
)
from app.services.config import ConfigService

router = APIRouter(prefix="/api/v1/configs", tags=["configs"])


def _to_version_summary(v: AgentConfigVersion | None) -> AgentConfigVersionSummary | None:
    if v is None:
        return None
    return AgentConfigVersionSummary(
        id=v.id,
        version_number=v.version_number,
        label=v.label,
        status=v.status,
        author=v.author,
        created_at=v.created_at,
    )


def _to_detail(c: AgentConfig, payload: ConfigPayload | None) -> AgentConfigDetail:
    return AgentConfigDetail(
        id=c.id,
        name=c.name,
        description=c.description,
        created_at=c.created_at,
        updated_at=c.updated_at,
        current_version=_to_version_summary(c.current_version),
        draft_version=_to_version_summary(c.draft_version),
        payload=payload,
    )


def _to_response(c: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        id=c.id,
        name=c.name,
        description=c.description,
        created_at=c.created_at,
        updated_at=c.updated_at,
        current_version=_to_version_summary(c.current_version),
        draft_version=_to_version_summary(c.draft_version),
    )


@router.post("", response_model=AgentConfigResponse, status_code=201)
def create_config(
    body: CreateConfigInput, session: SessionDep
) -> AgentConfigResponse:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    config = service.create_config(name=body.name, description=body.description)
    result = _to_response(config)
    session.commit()
    return result


@router.get("", response_model=AgentConfigPage)
def list_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Busca por nome (substring) ou ID exato"),
    status: ConfigPayloadStatus | None = Query(default=None),  # noqa: B008
    session: SessionDep,
) -> AgentConfigPage:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    items, total = service.list_configs(page=page, page_size=page_size, q=q, status=status)
    return AgentConfigPage(
        items=[_to_response(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{config_id}", response_model=AgentConfigDetail)
def get_config(config_id: UUID, session: SessionDep) -> AgentConfigDetail:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    try:
        config, payload = service.get_detail(config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_detail(config, payload)


@router.get("/{config_id}/versions", response_model=list[AgentConfigVersionDetail])
def list_versions(
    config_id: UUID, session: SessionDep
) -> list[AgentConfigVersionDetail]:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    try:
        versions = service.list_versions(config_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [
        AgentConfigVersionDetail(
            id=v.id,
            version_number=v.version_number,
            label=v.label,
            status=v.status,
            author=v.author,
            created_at=v.created_at,
            payload=ConfigPayload.model_validate(v.payload),
        )
        for v in versions
    ]


@router.post("/{config_id}/publish", response_model=AgentConfigVersionSummary, status_code=201)
def publish_draft(
    config_id: UUID, session: SessionDep
) -> AgentConfigVersionSummary:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    try:
        version = service.publish(config_id=config_id, author="panel")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    result = _to_version_summary(version)
    session.commit()
    return result  # type: ignore[return-value]


@router.post("/{config_id}/rollback", response_model=AgentConfigVersionSummary)
def rollback(
    config_id: UUID, body: RollbackInput, session: SessionDep
) -> AgentConfigVersionSummary:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    try:
        config = service.rollback(config_id=config_id, version_id=body.version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if config.current_version is None:
        raise HTTPException(status_code=500, detail="Estado inválido após rollback")
    result = _to_version_summary(config.current_version)
    session.commit()
    return result  # type: ignore[return-value]


@router.put("/{config_id}/draft", response_model=AgentConfigVersionSummary, status_code=201)
def save_draft(
    config_id: UUID, body: DraftInput, session: SessionDep
) -> AgentConfigVersionSummary:
    repo = ConfigRepository(session)
    service = ConfigService(repo)
    try:
        version = service.update_draft(
            config_id=config_id,
            name=body.name,
            description=body.description,
            payload=body.payload,
            author="panel",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    result = AgentConfigVersionSummary(
        id=version.id,
        version_number=version.version_number,
        label=version.label,
        status=version.status,
        author=version.author,
        created_at=version.created_at,
    )
    session.commit()
    return result
