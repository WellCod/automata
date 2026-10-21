"""Conectores de uma base (ADR-0024): cadastro, teste e sincronização em background."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.knowledge.connector_sync import selectable, source_of, sync
from app.knowledge.ingest import remove_chunks
from app.knowledge.schedule import next_at
from app.knowledge.sources import SourceError
from app.mcp.egress import EgressDenied, check_url
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_connector import KnowledgeConnector
from app.models.knowledge_content import KnowledgeContent
from app.schemas.knowledge_connector import (
    SECRET_FIELDS,
    SECRET_REQUIRED,
    SETTINGS_BY_KIND,
    ConnectorInput,
    ConnectorResponse,
    ConnectorTestResult,
)
from app.secrets import SecretsKeyMissing, encrypt_json
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{base_id}/connectors",
    tags=["knowledge-bases"],
    dependencies=[Depends(require_scopes(Scope.KNOWLEDGE_READ))],
)

# sincronizar usa a credencial salva: o editor da base pode; cadastrar e trocar, só owner
_SYNC = [Depends(require_scopes(Scope.KNOWLEDGE_WRITE))]
_OWNER = [Depends(require_scopes(Scope.KNOWLEDGE_CONNECTORS_WRITE))]


def _base_or_404(session: Session, base_id: UUID) -> KnowledgeBase:
    base = session.get(KnowledgeBase, base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="Base de conhecimento não encontrada")
    return base


def _connector_or_404(session: Session, base_id: UUID, connector_id: UUID) -> KnowledgeConnector:
    connector = session.get(KnowledgeConnector, connector_id)
    if connector is None or connector.base_id != base_id:
        raise HTTPException(status_code=404, detail="Conector não encontrado")
    return connector


def _response(session: Session, c: KnowledgeConnector) -> ConnectorResponse:
    count = session.scalar(
        select(func.count())
        .select_from(KnowledgeContent)
        .where(KnowledgeContent.connector_id == c.id)
    )
    return ConnectorResponse(
        id=c.id,
        base_id=c.base_id,
        kind=c.kind,
        name=c.name,
        settings=c.settings,
        has_secret=c.secret_encrypted is not None,
        last_status=c.last_status,
        last_message=c.last_message,
        last_summary=c.last_summary,
        last_sync_at=c.last_sync_at,
        sync_every_hours=c.sync_every_hours,
        next_sync_at=c.next_sync_at,
        content_count=int(count or 0),
        created_by=c.created_by,
        created_at=c.created_at,
    )


def _settings(body: ConnectorInput) -> dict[str, Any]:
    try:
        settings = SETTINGS_BY_KIND[body.kind].model_validate(body.settings)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
    data = settings.model_dump()
    # URL configurável sai pelo mesmo filtro dos servidores MCP
    for key in ("api_url", "endpoint_url"):
        if data.get(key):
            try:
                check_url(data[key])
            except EgressDenied as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    return data


def _sealed(kind: str, secret: dict[str, str]) -> str | None:
    unknown = sorted(set(secret) - set(SECRET_FIELDS[kind]))
    if unknown:
        raise HTTPException(status_code=422, detail=f"segredo com campo desconhecido: {unknown}")
    values = {k: v for k, v in secret.items() if v}
    if not values:
        return None
    try:
        return encrypt_json(values)
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _require_secret(kind: str, sealed: str | None) -> None:
    if sealed is None and SECRET_REQUIRED[kind]:
        raise HTTPException(status_code=422, detail=f"conector {kind} precisa de segredo")


@router.get("", response_model=list[ConnectorResponse])
def list_connectors(base_id: UUID, session: SessionDep) -> list[ConnectorResponse]:
    _base_or_404(session, base_id)
    rows = session.scalars(
        select(KnowledgeConnector)
        .where(KnowledgeConnector.base_id == base_id)
        .order_by(KnowledgeConnector.created_at)
    ).all()
    return [_response(session, c) for c in rows]


@router.post("", response_model=ConnectorResponse, status_code=201, dependencies=_OWNER)
def create_connector(
    base_id: UUID, body: ConnectorInput, request: Request, session: SessionDep
) -> ConnectorResponse:
    _base_or_404(session, base_id)
    settings = _settings(body)
    sealed = _sealed(body.kind, body.secret or {})
    _require_secret(body.kind, sealed)
    connector = KnowledgeConnector(
        base_id=base_id,
        kind=body.kind,
        name=body.name,
        settings=settings,
        secret_encrypted=sealed,
        created_by=str(getattr(request.state, "user_id", None) or "panel"),
        sync_every_hours=body.sync_every_hours,
        next_sync_at=next_at(body.sync_every_hours),
    )
    session.add(connector)
    session.commit()
    session.refresh(connector)
    return _response(session, connector)


@router.put("/{connector_id}", response_model=ConnectorResponse, dependencies=_OWNER)
def update_connector(
    base_id: UUID, connector_id: UUID, body: ConnectorInput, session: SessionDep
) -> ConnectorResponse:
    connector = _connector_or_404(session, base_id, connector_id)
    if body.kind != connector.kind:
        raise HTTPException(status_code=422, detail="o tipo do conector não muda; crie outro")
    settings = _settings(body)
    if body.secret is not None:
        sealed = _sealed(body.kind, body.secret)
        _require_secret(body.kind, sealed)
        connector.secret_encrypted = sealed
    connector.name = body.name
    connector.settings = settings
    if body.sync_every_hours != connector.sync_every_hours:
        connector.sync_every_hours = body.sync_every_hours
        connector.next_sync_at = next_at(body.sync_every_hours)
    session.commit()
    session.refresh(connector)
    return _response(session, connector)


@router.delete("/{connector_id}", status_code=204, dependencies=_OWNER)
def delete_connector(base_id: UUID, connector_id: UUID, session: SessionDep) -> Response:
    """Os conteúdos do conector saem com ele, e os trechos antes."""
    base = _base_or_404(session, base_id)
    connector = _connector_or_404(session, base_id, connector_id)
    contents = session.scalars(
        select(KnowledgeContent.id).where(KnowledgeContent.connector_id == connector_id)
    ).all()
    for content_id in contents:
        remove_chunks(base, content_id)
    session.delete(connector)
    session.commit()
    return Response(status_code=204)


@router.post("/{connector_id}/test", response_model=ConnectorTestResult, dependencies=_SYNC)
def test_connector(base_id: UUID, connector_id: UUID, session: SessionDep) -> ConnectorTestResult:
    """Lista a origem sem baixar nada: confere credencial, caminho e o que entraria."""
    connector = _connector_or_404(session, base_id, connector_id)
    try:
        listed = source_of(connector).list_files()
    except (SourceError, EgressDenied, SecretsKeyMissing) as exc:
        return ConnectorTestResult(ok=False, files=0, sample=[], error=str(exc))
    files, _ = selectable(listed, get_settings().knowledge_max_upload_mb * 1024 * 1024)
    return ConnectorTestResult(
        ok=True, files=len(files), sample=[f.path for f in files[:5]], error=None
    )


@router.post(
    "/{connector_id}/sync", response_model=ConnectorResponse, status_code=202, dependencies=_SYNC
)
def sync_connector(
    base_id: UUID, connector_id: UUID, session: SessionDep, background: BackgroundTasks
) -> ConnectorResponse:
    connector = _connector_or_404(session, base_id, connector_id)
    if connector.last_status == "running":
        raise HTTPException(status_code=409, detail="Sincronização em andamento")
    connector.last_status = "running"
    connector.last_message = None
    session.commit()
    session.refresh(connector)
    background.add_task(sync, connector.id)
    return _response(session, connector)
