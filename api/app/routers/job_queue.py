"""Fila durável dos runs em background, só para o owner (ADR-0037)."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app import job_queue
from app.authz import Scope, require_scopes
from app.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/queue",
    tags=["queue"],
    dependencies=[Depends(require_scopes(Scope.QUEUE_ADMIN))],
)


class QueueJob(BaseModel):
    id: str
    component_type: str | None
    component_id: str | None
    component_name: str | None
    status: str | None
    attempt: int
    max_attempts: int
    error: str | None
    user_id: str | None
    created_at: datetime | None
    completed_at: datetime | None


class QueueSummary(BaseModel):
    # falso com BACKGROUND_QUEUE_DURABLE=false: os runs em background ficam em memória
    durable: bool
    counts: dict[str, int]
    oldest_queued_at: datetime | None
    jobs: list[QueueJob]


@router.get("", response_model=QueueSummary)
def get_queue(session: SessionDep) -> QueueSummary:
    if not job_queue.durable():
        return QueueSummary(durable=False, counts={}, oldest_queued_at=None, jobs=[])
    data = job_queue.summary(session)
    return QueueSummary(durable=True, **data)


@router.post("/jobs/{job_id}/requeue", status_code=202)
def requeue_job(job_id: str, request: Request) -> dict[str, str]:
    if not job_queue.durable():
        raise HTTPException(status_code=409, detail="Fila durável desligada")
    if not job_queue.requeue(job_id):
        raise HTTPException(
            status_code=409, detail="Só job que falhou ou foi cancelado volta para a fila"
        )
    actor = str(getattr(request.state, "user_id", None) or "panel")
    logger.info("job recolocado na fila", extra={"job_id": job_id, "actor": actor})
    return {"status": "queued"}
