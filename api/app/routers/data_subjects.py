"""Direitos do titular (ADR-0032), só para o owner."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from app.authz import Scope, require_scopes
from app.data_subjects import inventory, purge_expired, run_export, subject_hash
from app.db import SessionDep
from app.models.data_subject import DataSubjectRequest

router = APIRouter(
    prefix="/api/v1",
    tags=["data-subjects"],
    dependencies=[Depends(require_scopes(Scope.DATA_SUBJECTS_ADMIN))],
)


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
    counts: dict[str, Any] | None
    error: str | None
    expires_at: datetime | None
    created_at: datetime
    finished_at: datetime | None


def _response(r: DataSubjectRequest) -> DataSubjectRequestResponse:
    return DataSubjectRequestResponse(
        id=r.id,
        kind=r.kind,
        subject=r.subject,
        subject_hash=r.subject_hash,
        status=r.status,
        requested_by=r.requested_by,
        counts=r.counts,
        error=r.error,
        expires_at=r.expires_at,
        created_at=r.created_at,
        finished_at=r.finished_at,
    )


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


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
    row = DataSubjectRequest(
        kind="export",
        subject=user_id,
        subject_hash=subject_hash(user_id),
        status="pending",
        requested_by=_actor(request),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    background.add_task(run_export, row.id)
    return _response(row)


@router.get("/data-subject-requests", response_model=list[DataSubjectRequestResponse])
def list_requests(session: SessionDep) -> list[DataSubjectRequestResponse]:
    purge_expired(session)
    rows = session.scalars(
        select(DataSubjectRequest).order_by(DataSubjectRequest.created_at.desc()).limit(100)
    ).all()
    return [_response(r) for r in rows]


@router.get(
    "/data-subject-requests/{request_id}/download",
    responses={200: {"content": {"application/gzip": {}}}},
)
def download(request_id: UUID, session: SessionDep) -> Response:
    purge_expired(session)
    row = session.get(DataSubjectRequest, request_id)
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
