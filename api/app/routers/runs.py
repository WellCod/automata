from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.config import ConfigRepository
from app.repositories.run import RunMetrics, RunRepository

router = APIRouter(
    prefix="/api/v1/configs",
    tags=["runs"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class AgentRunResponse(BaseModel):
    id: UUID
    agent_config_id: UUID
    user_id: str
    run_id: str | None
    status: str
    duration_ms: int | None
    error: str | None
    blocked_by: str | None = None
    # só em run de workflow: etapas que rodaram e consumo somado delas
    steps: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    created_at: datetime


class RunsPage(BaseModel):
    items: list[AgentRunResponse]
    total: int
    page: int
    page_size: int


class AgentMetricsResponse(BaseModel):
    total_runs: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    period_days: int
    blocked_runs: int = 0
    blocked_by: dict[str, int] = {}


def _parse_period(period: str) -> int:
    return int(period[:-1])


def _to_metrics_response(m: RunMetrics, blocked_by: dict[str, int]) -> AgentMetricsResponse:
    return AgentMetricsResponse(
        total_runs=m.total_runs,
        error_rate=m.error_rate,
        p50_ms=m.p50_ms,
        p95_ms=m.p95_ms,
        period_days=m.period_days,
        blocked_runs=m.blocked_runs,
        blocked_by=blocked_by,
    )


@router.get("/{config_id}/metrics", response_model=AgentMetricsResponse)
def get_metrics(
    config_id: UUID,
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
) -> AgentMetricsResponse:
    config_repo = ConfigRepository(session)
    if config_repo.get_config(config_id) is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")

    run_repo = RunRepository(session)
    days = _parse_period(period)
    since = datetime.now(UTC) - timedelta(days=days)
    return _to_metrics_response(
        run_repo.metrics(config_id, since=since, period_days=days),
        run_repo.blocked_by_rule(since=since, config_id=config_id),
    )


@router.get("/{config_id}/runs", response_model=RunsPage)
def list_runs(
    config_id: UUID,
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),  # noqa: B008
) -> RunsPage:
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")

    run_repo = RunRepository(session)
    runs, total = run_repo.list_by_config(config_id, page=page, page_size=page_size)
    # consumo do workflow é o das etapas, gravado nos agentes e times que rodaram
    consumo: dict[str, tuple[int | None, int | None, float | None]] = {}
    if config.kind == "workflow":
        found = run_repo.child_consumption([r.run_id for r in runs if r.run_id])
        consumo = {r.run_id or "": found.get(r.run_id or "", (0, 0, None)) for r in runs}
    return RunsPage(
        items=[
            AgentRunResponse(
                id=r.id,
                agent_config_id=r.agent_config_id,
                user_id=r.user_id,
                run_id=r.run_id,
                status=r.status,
                duration_ms=r.duration_ms,
                error=r.error,
                blocked_by=r.blocked_by,
                steps=consumo.get(r.run_id or "", (None, None, None))[0],
                total_tokens=consumo.get(r.run_id or "", (None, None, None))[1],
                cost=consumo.get(r.run_id or "", (None, None, None))[2],
                created_at=r.created_at,
            )
            for r in runs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
