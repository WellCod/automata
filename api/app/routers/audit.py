"""Leitura da trilha de auditoria (ADR-0041), só owner."""

import base64
import binascii
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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


def _encode(at: datetime, event_id: UUID) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{event_id}".encode()).decode()


def _decode(cursor: str) -> tuple[datetime, UUID]:
    try:
        at, event_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(at), UUID(event_id)
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
    more = len(rows) > limit
    rows = rows[:limit]
    actors = {r.actor for r in rows if r.actor}
    labels: dict[str, str] = dict(emails_by_id(session, actors))
    tokens: list[UUID] = []
    for value in actors:
        if value.startswith(_INTEGRATION):
            try:
                tokens.append(UUID(value.removeprefix(_INTEGRATION)))
            except ValueError:
                continue
    if tokens:
        for token in session.query(IntegrationToken).filter(IntegrationToken.id.in_(tokens)):
            labels[f"{_INTEGRATION}{token.id}"] = token.name
    config_ids = {r.config_id for r in rows if r.config_id}
    configs = (
        {
            str(c.id): AuditConfig(name=c.name, kind=str(c.kind))
            for c in session.scalars(select(AgentConfig).where(AgentConfig.id.in_(config_ids)))
        }
        if config_ids
        else {}
    )
    version_ids = _version_ids(rows)
    versions = (
        {
            str(v.id): v.version_number
            for v in session.scalars(
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
                id=r.id,
                created_at=r.created_at,
                actor=r.actor,
                actor_label=labels.get(r.actor) if r.actor else None,
                action=r.action,
                config_id=r.config_id,
                params=r.params,
                status_code=r.status_code,
                ip=r.ip,
                request_id=r.request_id,
                detail=r.detail,
            )
            for r in rows
        ],
        next_cursor=_encode(rows[-1].created_at, rows[-1].id) if more and rows else None,
    )
