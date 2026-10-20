from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.config import ConfigRepository
from app.repositories.embedding_usage import EmbeddingUsageRepository
from app.repositories.run import AgentRunSummary, DailyRunStats, RunRepository
from app.repositories.usage import AgentUsageSummary, DailyUsage, UsageRepository

router = APIRouter(
    prefix="/api/v1/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class GlobalMetricsSummary(BaseModel):
    total_runs: int
    error_rate: float
    # barrados por guardrail (ADR-0013), fora da taxa de erro
    blocked_runs: int = 0
    blocked_by: dict[str, int] = {}
    p50_ms: float | None
    p95_ms: float | None
    total_tokens: int
    total_cost: float | None
    # embeddings de bases de conhecimento: ingestão e buscas (ADR-0012), fora do total_cost
    embedding_tokens: int = 0
    embedding_cost: float | None = None
    # suítes de teste (ADR-0015): casos e juiz, fora do total_cost
    eval_tokens: int = 0
    eval_cost: float | None = None
    period_days: int


class AgentBreakdownItem(BaseModel):
    agent_config_id: UUID
    agent_name: str
    total_runs: int
    error_rate: float
    blocked_runs: int = 0
    total_tokens: int
    total_cost: float | None


MAX_SERIES_DAYS = 366


class DailyMetricsPoint(BaseModel):
    date: date
    total_runs: int
    error_count: int
    blocked_count: int = 0
    p50_ms: float | None
    p95_ms: float | None
    total_tokens: int
    total_cost: float | None


def build_series(
    first: date,
    last: date,
    runs: list[DailyRunStats],
    usage: list[DailyUsage],
) -> list[DailyMetricsPoint]:
    """Um ponto por dia de first a last; dia sem dado vem zerado (latência e custo nulos)."""
    runs_by_day = {r.day: r for r in runs}
    usage_by_day = {u.day: u for u in usage}
    points = []
    day = first
    while day <= last:
        run = runs_by_day.get(day)
        use = usage_by_day.get(day)
        points.append(
            DailyMetricsPoint(
                date=day,
                total_runs=run.total_runs if run else 0,
                error_count=run.error_count if run else 0,
                blocked_count=run.blocked_count if run else 0,
                p50_ms=run.p50_ms if run else None,
                p95_ms=run.p95_ms if run else None,
                total_tokens=use.total_tokens if use else 0,
                total_cost=use.total_cost if use else None,
            )
        )
        day += timedelta(days=1)
    return points


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
    embeddings = EmbeddingUsageRepository(session).summary(since=since, until=until)
    evals = usage_repo.eval_summary(since=since, until=until)

    return GlobalMetricsSummary(
        total_runs=metrics.total_runs,
        error_rate=metrics.error_rate,
        blocked_runs=metrics.blocked_runs,
        blocked_by=run_repo.blocked_by_rule(since=since, until=until),
        p50_ms=metrics.p50_ms,
        p95_ms=metrics.p95_ms,
        total_tokens=usage.total_tokens,
        total_cost=usage.total_cost,
        embedding_tokens=embeddings.tokens,
        embedding_cost=embeddings.cost,
        eval_tokens=evals.total_tokens,
        eval_cost=evals.total_cost,
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
    names = ConfigRepository(session).names_by_ids(list(all_ids))

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
                blocked_runs=run.blocked_count,
                total_tokens=usage.total_tokens,
                total_cost=usage.total_cost,
            )
        )
    return items


@router.get("/timeseries", response_model=list[DailyMetricsPoint])
def get_timeseries(
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
    start: date | None = Query(default=None),  # noqa: B008
    end: date | None = Query(default=None),  # noqa: B008
    agent_id: UUID | None = Query(default=None),  # noqa: B008
) -> list[DailyMetricsPoint]:
    since, until, _ = _resolve_range(period, start, end)
    last = (until or datetime.now(UTC)).date()
    if (last - since.date()).days > MAX_SERIES_DAYS:
        raise HTTPException(status_code=422, detail=f"Série limitada a {MAX_SERIES_DAYS} dias")
    runs = RunRepository(session).daily(since=since, until=until, config_id=agent_id)
    usage = UsageRepository(session).daily(since=since, until=until, agent_config_id=agent_id)
    return build_series(since.date(), last, runs, usage)
