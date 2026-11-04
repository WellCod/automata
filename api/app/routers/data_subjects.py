"""Direitos do titular (ADR-0032 e ADR-0036).

O owner pede por qualquer titular. Um token de integração com `data_subjects:request`
usa as mesmas rotas e só vê os pedidos que ele fez. Quem usa o painel pede os
próprios dados em `/me/data`.
"""

import contextlib
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from agno.os.scopes import has_required_scopes
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz import Scope
from app.data_subjects import (
    due_date,
    inventory,
    purge_expired,
    run_erase,
    run_export,
    subject_hash,
)
from app.db import SessionDep
from app.models.data_subject import DataSubjectRequest
from app.models.user import User

Source = Literal["panel", "integration", "self"]


def _scopes(request: Request) -> tuple[list[str], str | None]:
    return (
        list(getattr(request.state, "scopes", None) or []),
        getattr(request.state, "admin_scope", None),
    )


def _is_admin(request: Request) -> bool:
    """Owner, ou app sem autenticação (testes): vê todos os pedidos."""
    if not getattr(request.app.state, "enforce_scopes", False):
        return True
    scopes, admin = _scopes(request)
    return has_required_scopes(scopes, [Scope.DATA_SUBJECTS_ADMIN], admin_scope=admin)


def require_subject_access(request: Request) -> None:
    if _is_admin(request):
        return
    scopes, admin = _scopes(request)
    if not has_required_scopes(scopes, [Scope.DATA_SUBJECTS_REQUEST], admin_scope=admin):
        raise HTTPException(status_code=403, detail="Permissão insuficiente")


router = APIRouter(
    prefix="/api/v1",
    tags=["data-subjects"],
    dependencies=[Depends(require_subject_access)],
)
me_router = APIRouter(prefix="/api/v1/me/data", tags=["data-subjects"])


class SubjectInventory(BaseModel):
    user_id: str
    counts: dict[str, int]
    total: int


class DataSubjectRequestResponse(BaseModel):
    id: UUID
    kind: str
    # id em claro só enquanto o arquivo da exportação vale
    subject: str | None
    subject_hash: str
    status: str
    requested_by: str
    # panel (owner), integration (token) ou self (o próprio usuário do painel)
    source: str
    # prazo legal (ADR-0036)
    due_at: datetime | None = None
    counts: dict[str, Any] | None
    error: str | None
    expires_at: datetime | None
    created_at: datetime
    finished_at: datetime | None


def _emails(session: Session, ids: set[str]) -> dict[str, str]:
    """Quem pediu fica gravado pelo id do usuário; a resposta mostra o e-mail."""
    uuids = []
    for value in ids:
        with contextlib.suppress(TypeError, ValueError):
            uuids.append(UUID(value))
    if not uuids:
        return {}
    rows = session.execute(select(User.id, User.email).where(User.id.in_(uuids)))
    return {str(user_id): email for user_id, email in rows}


def _response(
    r: DataSubjectRequest, emails: dict[str, str] | None = None
) -> DataSubjectRequestResponse:
    return DataSubjectRequestResponse(
        id=r.id,
        kind=r.kind,
        subject=r.subject,
        subject_hash=r.subject_hash,
        status=r.status,
        requested_by=(emails or {}).get(r.requested_by, r.requested_by),
        source=r.source,
        due_at=r.due_at,
        counts=r.counts,
        error=r.error,
        expires_at=r.expires_at,
        created_at=r.created_at,
        finished_at=r.finished_at,
    )


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _source(actor: str) -> Source:
    return "integration" if actor.startswith("integration:") else "panel"


def create_export(
    session: Session, user_id: str, actor: str, source: Source, background: BackgroundTasks
) -> DataSubjectRequest:
    row = DataSubjectRequest(
        kind="export",
        subject=user_id,
        subject_hash=subject_hash(user_id),
        status="pending",
        requested_by=actor,
        source=source,
        due_at=due_date(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    background.add_task(run_export, row.id)
    return row


def create_erase(
    session: Session, user_id: str, actor: str, source: Source, background: BackgroundTasks
) -> DataSubjectRequest:
    row = DataSubjectRequest(
        kind="erase",
        subject=None,
        subject_hash=subject_hash(user_id),
        status="pending",
        requested_by=actor,
        source=source,
        due_at=due_date(),
    )
    session.add(row)
    # exportação do mesmo titular também perde o arquivo e o id em claro
    for pending in session.scalars(
        select(DataSubjectRequest).where(
            DataSubjectRequest.kind == "export",
            DataSubjectRequest.subject_hash == row.subject_hash,
        )
    ):
        pending.result = None
        pending.subject = None
        pending.expires_at = None
        if pending.status == "done":
            pending.status = "expired"
    session.commit()
    session.refresh(row)
    # o id em claro só existe no argumento do background
    background.add_task(run_erase, row.id, user_id)
    return row


def _download(row: DataSubjectRequest | None) -> Response:
    if row is None or row.kind != "export":
        raise HTTPException(status_code=404, detail="Exportação não encontrada")
    if row.status != "done" or row.result is None:
        raise HTTPException(status_code=409, detail="Exportação ainda não pronta ou vencida")
    stamp = (row.finished_at or datetime.now(UTC)).strftime("%Y%m%d")
    filename = f"titular-{row.subject_hash[:12]}-{stamp}.json.gz"
    return Response(
        content=row.result,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/data-subjects/{user_id}", response_model=SubjectInventory)
def get_subject(user_id: str) -> SubjectInventory:
    counts = inventory(user_id)
    return SubjectInventory(user_id=user_id, counts=counts, total=sum(counts.values()))


@router.post(
    "/data-subjects/{user_id}/export",
    response_model=DataSubjectRequestResponse,
    status_code=202,
)
def export_subject(
    user_id: str, session: SessionDep, request: Request, background: BackgroundTasks
) -> DataSubjectRequestResponse:
    actor = _actor(request)
    return _response(create_export(session, user_id, actor, _source(actor), background))


class EraseInput(BaseModel):
    # o id repetido no corpo: apagar um titular não tem volta
    confirm: str


@router.post(
    "/data-subjects/{user_id}/erase",
    response_model=DataSubjectRequestResponse,
    status_code=202,
)
def erase_subject(
    user_id: str,
    body: EraseInput,
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
) -> DataSubjectRequestResponse:
    if body.confirm != user_id:
        raise HTTPException(status_code=422, detail="Repita o id do titular para confirmar")
    actor = _actor(request)
    return _response(create_erase(session, user_id, actor, _source(actor), background))


@router.get("/data-subject-requests", response_model=list[DataSubjectRequestResponse])
def list_requests(session: SessionDep, request: Request) -> list[DataSubjectRequestResponse]:
    purge_expired(session)
    query = select(DataSubjectRequest)
    if not _is_admin(request):
        # o token de integração vê só os pedidos dele
        query = query.where(DataSubjectRequest.requested_by == _actor(request))
    rows = session.scalars(query.order_by(DataSubjectRequest.created_at.desc()).limit(100)).all()
    emails = _emails(session, {r.requested_by for r in rows})
    return [_response(r, emails) for r in rows]


@router.get(
    "/data-subject-requests/{request_id}/download",
    responses={200: {"content": {"application/gzip": {}}}},
)
def download(request_id: UUID, session: SessionDep, request: Request) -> Response:
    purge_expired(session)
    row = session.get(DataSubjectRequest, request_id)
    if row is not None and not _is_admin(request) and row.requested_by != _actor(request):
        row = None
    return _download(row)


# --- o próprio usuário do painel (ADR-0036) ---


def _me(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id or str(user_id).startswith("integration:"):
        raise HTTPException(status_code=401, detail="Sem usuário do painel no token")
    return str(user_id)


class MeEraseInput(BaseModel):
    # o e-mail da conta repetido: o id do titular é um UUID que ninguém decora
    confirm: str


@me_router.get("", response_model=SubjectInventory)
def my_inventory(request: Request) -> SubjectInventory:
    user_id = _me(request)
    counts = inventory(user_id)
    return SubjectInventory(user_id=user_id, counts=counts, total=sum(counts.values()))


@me_router.post("/export", response_model=DataSubjectRequestResponse, status_code=202)
def my_export(
    session: SessionDep, request: Request, background: BackgroundTasks
) -> DataSubjectRequestResponse:
    user_id = _me(request)
    return _response(create_export(session, user_id, user_id, "self", background))


@me_router.post("/erase", response_model=DataSubjectRequestResponse, status_code=202)
def my_erase(
    body: MeEraseInput, session: SessionDep, request: Request, background: BackgroundTasks
) -> DataSubjectRequestResponse:
    user_id = _me(request)
    user = session.get(User, UUID(user_id)) if _is_uuid(user_id) else None
    if user is None or body.confirm.strip().lower() != user.email.lower():
        raise HTTPException(status_code=422, detail="Repita o seu e-mail para confirmar")
    return _response(create_erase(session, user_id, user_id, "self", background))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


@me_router.get("/requests", response_model=list[DataSubjectRequestResponse])
def my_requests(session: SessionDep, request: Request) -> list[DataSubjectRequestResponse]:
    user_id = _me(request)
    purge_expired(session)
    rows = session.scalars(
        select(DataSubjectRequest)
        .where(
            DataSubjectRequest.requested_by == user_id,
            DataSubjectRequest.source == "self",
        )
        .order_by(DataSubjectRequest.created_at.desc())
        .limit(50)
    ).all()
    return [_response(r) for r in rows]


@me_router.get(
    "/requests/{request_id}/download",
    responses={200: {"content": {"application/gzip": {}}}},
)
def my_download(request_id: UUID, session: SessionDep, request: Request) -> Response:
    user_id = _me(request)
    purge_expired(session)
    row = session.get(DataSubjectRequest, request_id)
    if row is not None and (row.requested_by != user_id or row.source != "self"):
        row = None
    return _download(row)
