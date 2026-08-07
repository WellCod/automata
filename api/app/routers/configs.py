from fastapi import APIRouter, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.schemas.config import (
    AgentConfigPage,
    AgentConfigResponse,
    AgentConfigVersionSummary,
    ConfigPayloadStatus,
)
from app.services.config import ConfigService
from app.settings import get_settings

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


@router.get("", response_model=AgentConfigPage)
def list_configs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Busca por nome (substring) ou ID exato"),
    status: ConfigPayloadStatus | None = Query(default=None),  # noqa: B008
) -> AgentConfigPage:
    engine = create_engine(get_settings().database_url)
    with Session(engine) as session:
        repo = ConfigRepository(session)
        service = ConfigService(repo)
        items, total = service.list_configs(page=page, page_size=page_size, q=q, status=status)
        response_items = [_to_response(c) for c in items]
    return AgentConfigPage(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
    )
