"""Árvore de execução de um run: líder → membros → modelo e tools.

Lê os spans que o tracing do AgentOS grava no banco e devolve em formato
tipado para o painel; as rotas /traces do Agno ficam fora do OpenAPI que
gera os tipos do client.
"""

from datetime import datetime
from typing import Any

from agno.os.routers.traces.schemas import TraceDetail
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.authz import Scope, require_scopes, sees_everyone

router = APIRouter(
    prefix="/api/v1/runs",
    tags=["traces"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class TraceSpan(BaseModel):
    id: str
    name: str
    # AGENT, TEAM, LLM, TOOL…
    type: str
    duration: str
    status: str
    start_time: datetime
    end_time: datetime
    input: str | None = None
    output: str | None = None
    error: str | None = None
    spans: list["TraceSpan"] = Field(default_factory=list)

    @field_validator("spans", mode="before")
    @classmethod
    def folha_sem_filhos(cls, v: Any) -> Any:
        # o Agno manda None nas folhas
        return v or []


class RunTrace(BaseModel):
    trace_id: str
    run_id: str | None
    status: str
    duration: str
    total_spans: int
    error_count: int
    tree: list[TraceSpan]


def _load(db: Any, run_id: str) -> TraceDetail | None:
    trace = db.get_trace(run_id=run_id)
    if trace is None:
        return None
    return TraceDetail.from_trace_and_spans(trace, db.get_spans(trace_id=trace.trace_id))


@router.get("/{run_id}/trace", response_model=RunTrace)
async def get_run_trace(run_id: str, request: Request) -> RunTrace:
    db = getattr(request.app.state, "agno_db", None)
    if db is None:
        raise HTTPException(status_code=404, detail="Tracing desligado")
    detail = await run_in_threadpool(_load, db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace não encontrado para este run")
    # trace traz entrada e saída da conversa: mesma regra do Agno, só o dono ou admin
    owner = detail.user_id == getattr(request.state, "user_id", None)
    if not sees_everyone(request) and not owner:
        raise HTTPException(status_code=403, detail="Permissão insuficiente")
    data = detail.model_dump()
    return RunTrace(
        trace_id=data["trace_id"],
        run_id=data.get("run_id"),
        status=data["status"],
        duration=data["duration"],
        total_spans=data["total_spans"],
        error_count=data["error_count"],
        tree=[TraceSpan.model_validate(node) for node in data["tree"]],
    )
