from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import SessionDep
from app.repositories.run import RunRepository
from app.repositories.usage import UsageRepository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class GlobalMetricsSummary(BaseModel):
    total_runs: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    total_tokens: int
    total_cost: float | None
    period_days: int


@router.get("/summary", response_model=GlobalMetricsSummary)
def get_summary(
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
) -> GlobalMetricsSummary:
    period_days = int(period[:-1])

    run_repo = RunRepository(session)
    metrics = run_repo.metrics_global(period_days=period_days)

    usage_repo = UsageRepository(session)
    usage = usage_repo.usage_summary(period_days=period_days)

    return GlobalMetricsSummary(
        total_runs=metrics.total_runs,
        error_rate=metrics.error_rate,
        p50_ms=metrics.p50_ms,
        p95_ms=metrics.p95_ms,
        total_tokens=usage.total_tokens,
        total_cost=usage.total_cost,
        period_days=period_days,
    )
