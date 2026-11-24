"""Direitos do titular (ADR-0032 e ADR-0036).

O owner pede por qualquer titular. Um token de integração com `data_subjects:request`
usa as mesmas rotas só pelo próprio titular, `integration:<id>`, e só vê os pedidos que ele
fez. Quem usa o painel pede os próprios dados em `/me/data`.
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

from app.authz import Scope, scopes_enforced
from app.data_subjects import (
    due_date,
    inventory,
    new_erase_request,
    purge_expired,
    run_erase,
    run_export,
    subject_hash,
)
from app.db import SessionDep
from app.models.data_subject import DataSubjectRequest
from app.models.user import User

Source = Literal["panel", "integration", "self", "channel"]


def _scopes(request: Request) -> tuple[list[str], str | None]:
    """Scopes do token e o scope de admin, como o middleware de autorização deixou."""
    return (
        list(getattr(request.state, "scopes", None) or []),
        getattr(request.state, "admin_scope", None),
    )


def _is_admin(request: Request) -> bool:
    """Owner, ou app sem autenticação (testes): vê todos os pedidos."""
    if not scopes_enforced(request):
        return True
    scopes, admin_scope = _scopes(request)
    return has_required_scopes(scopes, [Scope.DATA_SUBJECTS_ADMIN], admin_scope=admin_scope)


def _own_subject(request: Request, user_id: str) -> None:
    """Token de integração só pede pelo próprio titular (ADR-0036, revisto na Fase 43).

    Com `user_isolation`, o Agno grava todo run do token como `integration:<id>`; aceitar
    outro id dava a ele as conversas de outras integrações e do painel.
    """
    if not _is_admin(request) and user_id != _actor(request):
        raise HTTPException(status_code=403, detail="O token só pede pelo próprio titular")


def require_subject_access(request: Request) -> None:
    """Owner passa direto; token de integração precisa de `data_subjects:request`."""
    if _is_admin(request):
        return
    scopes, admin_scope = _scopes(request)
    if not has_required_scopes(scopes, [Scope.DATA_SUBJECTS_REQUEST], admin_scope=admin_scope):
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


def _emails(session: Session, user_ids: set[str]) -> dict[str, str]:
    """Quem pediu fica gravado pelo id do usuário; a resposta mostra o e-mail."""
    valid_ids = []
    for user_id in user_ids:
        with contextlib.suppress(TypeError, ValueError):
            valid_ids.append(UUID(user_id))
    if not valid_ids:
        return {}
    rows = session.execute(select(User.id, User.email).where(User.id.in_(valid_ids)))
    return {str(user_id): email for user_id, email in rows}


def _response(
    subject_request: DataSubjectRequest, emails: dict[str, str] | None = None
) -> DataSubjectRequestResponse:
    """Pedido com o e-mail de quem pediu no lugar do id, quando é usuário do painel."""
    return DataSubjectRequestResponse(
        id=subject_request.id,
        kind=subject_request.kind,
        subject=subject_request.subject,
        subject_hash=subject_request.subject_hash,
        status=subject_request.status,
        requested_by=(emails or {}).get(subject_request.requested_by, subject_request.requested_by),
        source=subject_request.source,
        due_at=subject_request.due_at,
        counts=subject_request.counts,
        error=subject_request.error,
        expires_at=subject_request.expires_at,
        created_at=subject_request.created_at,
        finished_at=subject_request.finished_at,
    )


def _actor(request: Request) -> str:
    """Quem pediu; "panel" quando a requisição não traz usuário."""
    return str(getattr(request.state, "user_id", None) or "panel")


def _source(actor: str) -> Source:
    """Origem do pedido pelo autor: token de integração ou owner no painel."""
    return "integration" if actor.startswith("integration:") else "panel"


def create_export(
    session: Session, user_id: str, actor: str, source: Source, background: BackgroundTasks
) -> DataSubjectRequest:
    """Registra o pedido de exportação e monta o arquivo em background."""
    subject_request = DataSubjectRequest(
        kind="export",
        subject=user_id,
        subject_hash=subject_hash(user_id),
        status="pending",
        requested_by=actor,
        source=source,
        due_at=due_date(),
    )
    session.add(subject_request)
    session.commit()
    session.refresh(subject_request)
    background.add_task(run_export, subject_request.id)
    return subject_request


def create_erase(
    session: Session, user_id: str, actor: str, source: Source, background: BackgroundTasks
) -> DataSubjectRequest:
    """Registra o pedido de exclusão e apaga os dados do titular em background."""
    # exportação do mesmo titular também perde o arquivo e o id em claro
    request_id = new_erase_request(session, user_id, actor, source)
    subject_request = session.get(DataSubjectRequest, request_id)
    assert subject_request is not None
    # o id em claro só existe no argumento do background
    background.add_task(run_erase, subject_request.id, user_id)
    return subject_request


def _download(export_request: DataSubjectRequest | None) -> Response:
    """Arquivo da exportação pronta; o nome leva só o hash do titular, nunca o id."""
    if export_request is None or export_request.kind != "export":
        raise HTTPException(status_code=404, detail="Exportação não encontrada")
    if export_request.status != "done" or export_request.result is None:
        raise HTTPException(status_code=409, detail="Exportação ainda não pronta ou vencida")
    date_stamp = (export_request.finished_at or datetime.now(UTC)).strftime("%Y%m%d")
    filename = f"titular-{export_request.subject_hash[:12]}-{date_stamp}.json.gz"
    return Response(
        content=export_request.result,
        media_type="application/gzip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/data-subjects/{user_id}", response_model=SubjectInventory)
def get_subject(user_id: str, request: Request) -> SubjectInventory:
    """Quanto de cada tipo de dado existe do titular, sem o conteúdo."""
    _own_subject(request, user_id)
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
    _own_subject(request, user_id)
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
    _own_subject(request, user_id)
    if body.confirm != user_id:
        raise HTTPException(status_code=422, detail="Repita o id do titular para confirmar")
    actor = _actor(request)
    return _response(create_erase(session, user_id, actor, _source(actor), background))


@router.get("/data-subject-requests", response_model=list[DataSubjectRequestResponse])
def list_requests(session: SessionDep, request: Request) -> list[DataSubjectRequestResponse]:
    """Últimos 100 pedidos, depois de apagar os arquivos de exportação vencidos."""
    purge_expired(session)
    query = select(DataSubjectRequest)
    if not _is_admin(request):
        # o token de integração vê só os pedidos dele
        query = query.where(DataSubjectRequest.requested_by == _actor(request))
    rows = session.scalars(query.order_by(DataSubjectRequest.created_at.desc()).limit(100)).all()
    emails = _emails(session, {subject_request.requested_by for subject_request in rows})
    return [_response(subject_request, emails) for subject_request in rows]


@router.get(
    "/data-subject-requests/{request_id}/download",
    responses={200: {"content": {"application/gzip": {}}}},
)
def download(request_id: UUID, session: SessionDep, request: Request) -> Response:
    """Baixa a exportação; pedido de outro autor responde como inexistente."""
    purge_expired(session)
    export_request = session.get(DataSubjectRequest, request_id)
    if (
        export_request is not None
        and not _is_admin(request)
        and export_request.requested_by != _actor(request)
    ):
        export_request = None
    return _download(export_request)


# --- o próprio usuário do painel (ADR-0036) ---


def _me(request: Request) -> str:
    """Id do usuário do painel; token de integração não usa as rotas de `/me/data`."""
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
    return [_response(subject_request) for subject_request in rows]


@me_router.get(
    "/requests/{request_id}/download",
    responses={200: {"content": {"application/gzip": {}}}},
)
def my_download(request_id: UUID, session: SessionDep, request: Request) -> Response:
    """Baixa a exportação que o próprio usuário pediu; a de outro responde como inexistente."""
    user_id = _me(request)
    purge_expired(session)
    export_request = session.get(DataSubjectRequest, request_id)
    if export_request is not None and (
        export_request.requested_by != user_id or export_request.source != "self"
    ):
        export_request = None
    return _download(export_request)
