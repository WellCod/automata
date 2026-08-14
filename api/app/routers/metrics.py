from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.models.config import AgentConfig
from app.repositories.run import AgentRunSummary, RunRepository
from app.repositories.usage import AgentUsageSummary, UsageRepository

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


class GlobalMetricsSummary(BaseModel):
    total_runs: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    total_tokens: int
    total_cost: float | None
    period_days: int


class AgentBreakdownItem(BaseModel):
    agent_config_id: UUID
    agent_name: str
    total_runs: int
    error_rate: float
    total_tokens: int
    total_cost: float | None


def _parse_period(period: str) -> int:
    return int(period[:-1])


def _resolve_range(
    period: str,
    start: date | None,
    end: date | None,
) -> tuple[datetime, datetime | None, int]:
    if start is not None:
        since = datetime(start.year, start.month, start.day, tzinfo=UTC)
        until = (
            datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=UTC)
            if end is not None
            else None
        )
        period_days = (end - start).days + 1 if end is not None else 0
        return since, until, period_days
    period_days = _parse_period(period)
    return datetime.now(UTC) - timedelta(days=period_days), None, period_days


@router.get("/summary", response_model=GlobalMetricsSummary)
def get_summary(
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
    start: date | None = Query(default=None),  # noqa: B008
    end: date | None = Query(default=None),  # noqa: B008
) -> GlobalMetricsSummary:
    since, until, period_days = _resolve_range(period, start, end)

    run_repo = RunRepository(session)
    metrics = run_repo.metrics_global(since=since, until=until, period_days=period_days)

    usage_repo = UsageRepository(session)
    usage = usage_repo.usage_summary(since=since, until=until, period_days=period_days)

    return GlobalMetricsSummary(
        total_runs=metrics.total_runs,
        error_rate=metrics.error_rate,
        p50_ms=metrics.p50_ms,
        p95_ms=metrics.p95_ms,
        total_tokens=usage.total_tokens,
        total_cost=usage.total_cost,
        period_days=period_days,
    )


@router.get("/by-agent", response_model=list[AgentBreakdownItem])
def get_by_agent(
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
    start: date | None = Query(default=None),  # noqa: B008
    end: date | None = Query(default=None),  # noqa: B008
) -> list[AgentBreakdownItem]:
    since, until, period_days = _resolve_range(period, start, end)

    runs_by_id: dict[UUID, AgentRunSummary] = {
        r.agent_config_id: r
        for r in RunRepository(session).runs_by_agent(
            since=since, until=until, period_days=period_days
        )
    }
    usage_by_id: dict[UUID, AgentUsageSummary] = {
        u.agent_config_id: u
        for u in UsageRepository(session).usage_by_agent(
            since=since, until=until, period_days=period_days
        )
    }

    all_ids = runs_by_id.keys() | usage_by_id.keys()
    names: dict[UUID, str] = {
        row.id: row.name
        for row in session.execute(
            select(AgentConfig.id, AgentConfig.name).where(AgentConfig.id.in_(list(all_ids)))
        ).all()
    }

    def _run_count(i: UUID) -> int:
        return -(runs_by_id.get(i, AgentRunSummary(i, 0, 0)).total_runs)

    items = []
    for agent_id in sorted(all_ids, key=_run_count):
        run = runs_by_id.get(agent_id, AgentRunSummary(agent_id, 0, 0))
        usage = usage_by_id.get(agent_id, AgentUsageSummary(agent_id, 0, None))
        items.append(
            AgentBreakdownItem(
                agent_config_id=agent_id,
                agent_name=names.get(agent_id, str(agent_id)[:8]),
                total_runs=run.total_runs,
                error_rate=run.error_count / run.total_runs if run.total_runs > 0 else 0.0,
                total_tokens=usage.total_tokens,
                total_cost=usage.total_cost,
            )
        )
    return items
