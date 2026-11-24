"""Leitura da trilha de auditoria (ADR-0041), só owner."""

import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select

from app import audit
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.config import AgentConfig, AgentConfigVersion
from app.models.integration import IntegrationToken
from app.repositories.user import emails_by_id

router = APIRouter(
    prefix="/api/v1/audit",
    tags=["audit"],
    dependencies=[Depends(require_scopes(Scope.AUDIT_READ))],
)

_INTEGRATION = "integration:"


class AuditEventResponse(BaseModel):
    id: UUID
    created_at: datetime
    actor: str | None
    # e-mail do usuário ou nome do token; vazio quando quem fez já não existe
    actor_label: str | None
    action: str
    config_id: UUID | None
    params: dict[str, Any] | None
    status_code: int
    ip: str | None
    request_id: str | None
    detail: dict[str, Any] | None


class AuditConfig(BaseModel):
    name: str
    kind: str


class AuditPage(BaseModel):
    items: list[AuditEventResponse]
    next_cursor: str | None
    # nome dos configs e número das versões citadas na página, para a tela não mostrar uuid
    configs: dict[str, AuditConfig]
    versions: dict[str, int]


_VERSION_KEYS = ("current_before", "current_after", "canary_version")


def _version_ids(rows: list[Any]) -> set[UUID]:
    """Ids de versão citados no detalhe dos eventos (rollback e canário), para virar número."""
    found: set[UUID] = set()
    for row in rows:
        for key in _VERSION_KEYS:
            value = (row.detail or {}).get(key)
            if isinstance(value, str):
                try:
                    found.add(UUID(value))
                except ValueError:
                    continue
    return found


def _encode(created_at: datetime, event_id: UUID) -> str:
    """Cursor opaco da paginação: data e id do último evento da página."""
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{event_id}".encode()).decode()


def _decode(cursor: str) -> tuple[datetime, UUID]:
    """Lê o cursor de `_encode`; cursor adulterado vira 422, não 500."""
    try:
        created_at, event_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(created_at), UUID(event_id)
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Cursor inválido") from exc


@router.get("", response_model=AuditPage)
def list_events(
    session: SessionDep,
    actor: str | None = Query(default=None, max_length=128),
    config_id: UUID | None = None,
    action: str | None = Query(default=None, max_length=100),
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
) -> AuditPage:
    """Página da trilha, mais recente primeiro, com quem fez e configs e versões por nome."""
    # um a mais que o limite só para saber se existe próxima página
    rows = audit.page(
        session,
        actor=actor,
        config_id=config_id,
        action=action,
        since=since,
        until=until,
        before=_decode(cursor) if cursor else None,
        limit=limit + 1,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    actors = {event.actor for event in rows if event.actor}
    labels: dict[str, str] = dict(emails_by_id(session, actors))
    # token de integração aparece como `integration:<id>`; o rótulo é o nome do token
    token_ids: list[UUID] = []
    for actor_id in actors:
        if actor_id.startswith(_INTEGRATION):
            try:
                token_ids.append(UUID(actor_id.removeprefix(_INTEGRATION)))
            except ValueError:
                continue
    if token_ids:
        for token in session.query(IntegrationToken).filter(IntegrationToken.id.in_(token_ids)):
            labels[f"{_INTEGRATION}{token.id}"] = token.name
    config_ids = {event.config_id for event in rows if event.config_id}
    configs = (
        {
            str(config.id): AuditConfig(name=config.name, kind=str(config.kind))
            for config in session.scalars(select(AgentConfig).where(AgentConfig.id.in_(config_ids)))
        }
        if config_ids
        else {}
    )
    version_ids = _version_ids(rows)
    versions = (
        {
            str(version.id): version.version_number
            for version in session.scalars(
                select(AgentConfigVersion).where(AgentConfigVersion.id.in_(version_ids))
            )
        }
        if version_ids
        else {}
    )
    return AuditPage(
        configs=configs,
        versions=versions,
        items=[
            AuditEventResponse(
                id=event.id,
                created_at=event.created_at,
                actor=event.actor,
                actor_label=labels.get(event.actor) if event.actor else None,
                action=event.action,
                config_id=event.config_id,
                params=event.params,
                status_code=event.status_code,
                ip=event.ip,
                request_id=event.request_id,
                detail=event.detail,
            )
            for event in rows
        ],
        next_cursor=_encode(rows[-1].created_at, rows[-1].id) if has_more and rows else None,
    )


_EXPORT_MAX = 50_000


@router.get("/export", response_class=Response)
def export_events(
    session: SessionDep,
    actor: str | None = Query(default=None, max_length=128),
    config_id: UUID | None = None,
    action: str | None = Query(default=None, max_length=100),
    since: datetime | None = None,
    until: datetime | None = None,
) -> Response:
    """A trilha filtrada em CSV, até 50 mil linhas, para a auditoria do cliente (COM-07)."""
    import csv
    import io
    import json

    rows = audit.page(
        session,
        actor=actor,
        config_id=config_id,
        action=action,
        since=since,
        until=until,
        before=None,
        limit=_EXPORT_MAX,
    )
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, delimiter=";")
    writer.writerow(["quando", "quem", "acao", "config", "status", "ip", "request_id", "detalhe"])
    for event in rows:
        values = [
            event.created_at.isoformat(),
            event.actor or "",
            event.action,
            str(event.config_id or ""),
            event.status_code,
            event.ip or "",
            event.request_id or "",
            json.dumps(event.detail, ensure_ascii=False) if event.detail else "",
        ]
        # célula começando com = + - @ vira fórmula no Excel
        writer.writerow(
            [
                "'" + value
                if isinstance(value, str) and value[:1] in ("=", "+", "-", "@")
                else value
                for value in values
            ]
        )
    return Response(
        content="\ufeff" + csv_buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="trilha-de-auditoria.csv"'},
    )
