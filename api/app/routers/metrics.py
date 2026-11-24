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
    runs_by_day = {day_runs.day: day_runs for day_runs in runs}
    usage_by_day = {day_usage.day: day_usage for day_usage in usage}
    points = []
    day = first
    while day <= last:
        day_runs = runs_by_day.get(day)
        day_usage = usage_by_day.get(day)
        points.append(
            DailyMetricsPoint(
                date=day,
                total_runs=day_runs.total_runs if day_runs else 0,
                error_count=day_runs.error_count if day_runs else 0,
                blocked_count=day_runs.blocked_count if day_runs else 0,
                p50_ms=day_runs.p50_ms if day_runs else None,
                p95_ms=day_runs.p95_ms if day_runs else None,
                total_tokens=day_usage.total_tokens if day_usage else 0,
                total_cost=day_usage.total_cost if day_usage else None,
            )
        )
        day += timedelta(days=1)
    return points


def _parse_period(period: str) -> int:
    """Dias de um período como `30d`, entre 1 e o teto da série."""
    # `99999d` varria a tabela inteira, e um número enorme estourava a data (Fase 44)
    return max(1, min(int(period[:-1][:6]), MAX_SERIES_DAYS))


def _resolve_range(
    period: str,
    start: date | None,
    end: date | None,
) -> tuple[datetime, datetime | None, int]:
    """Início, fim e número de dias: datas explícitas valem mais que o período relativo.

    Sem `end`, o intervalo fica aberto até agora e o número de dias vem zero.
    """
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
    """Totais da instância no período: runs, latência, bloqueios e custo por origem."""
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
    """Runs e custo por agente no período, do que mais rodou para o que menos rodou."""
    since, until, period_days = _resolve_range(period, start, end)

    runs_by_id: dict[UUID, AgentRunSummary] = {
        run_summary.agent_config_id: run_summary
        for run_summary in RunRepository(session).runs_by_agent(
            since=since, until=until, period_days=period_days
        )
    }
    usage_by_id: dict[UUID, AgentUsageSummary] = {
        usage_summary.agent_config_id: usage_summary
        for usage_summary in UsageRepository(session).usage_by_agent(
            since=since, until=until, period_days=period_days
        )
    }

    # agente com consumo e sem run (ou o contrário) também entra na lista
    all_ids = runs_by_id.keys() | usage_by_id.keys()
    names = ConfigRepository(session).names_by_ids(list(all_ids))

    def _run_count(config_id: UUID) -> int:
        """Chave de ordenação: negativo para o que mais rodou vir primeiro."""
        return -(runs_by_id.get(config_id, AgentRunSummary(config_id, 0, 0)).total_runs)

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
    """Série diária da instância ou de um agente, com no máximo um ano de dias."""
    since, until, _ = _resolve_range(period, start, end)
    last_day = (until or datetime.now(UTC)).date()
    if (last_day - since.date()).days > MAX_SERIES_DAYS:
        raise HTTPException(status_code=422, detail=f"Série limitada a {MAX_SERIES_DAYS} dias")
    runs = RunRepository(session).daily(since=since, until=until, config_id=agent_id)
    usage = UsageRepository(session).daily(since=since, until=until, agent_config_id=agent_id)
    return build_series(since.date(), last_day, runs, usage)


class ReconciliationRow(BaseModel):
    provider: str
    day: date
    reported_usd: float
    estimated_usd: float
    diff_usd: float
    diff_percent: float | None
    # o dia corrente ainda recebe custo do provedor
    closed: bool
    fetched_at: datetime


class Reconciliation(BaseModel):
    # provedores com chave admin no ambiente (ANTHROPIC_ADMIN_KEY, OPENAI_ADMIN_KEY)
    providers: list[str]
    alert_percent: float
    rows: list[ReconciliationRow]


@router.get("/reconciliation", response_model=Reconciliation)
def get_reconciliation(
    session: SessionDep, days: int = Query(default=30, ge=1, le=90)
) -> Reconciliation:
    """Custo informado pelo provedor e estimado pelo Automata, por dia (ADR-0037)."""
    from app import reconciliation

    today = datetime.now(UTC).date()
    return Reconciliation(
        providers=sorted(reconciliation.configured()),
        alert_percent=reconciliation.alert_percent(),
        rows=[
            ReconciliationRow(**report_row)
            for report_row in reconciliation.report(session, days, today)
        ],
    )
