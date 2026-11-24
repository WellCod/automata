from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.authz import Scope, require_scopes, sees_everyone
from app.db import SessionDep
from app.repositories.config import ConfigRepository
from app.repositories.run import RunMetrics, RunRepository


def masked_user(user_id: str | None) -> str | None:
    """Quem não é owner vê só o canal e o fim do id: telefone e e-mail são dado pessoal."""
    if not user_id:
        return user_id
    # `whatsapp:5511999990000` vira `whatsapp:•••0000`; id curto não mostra nem o fim
    channel_prefix, separator, identifier = user_id.rpartition(":")
    tail = identifier[-4:] if len(identifier) > 4 else ""
    return f"{channel_prefix}{separator}•••{tail}"


router = APIRouter(
    prefix="/api/v1/configs",
    tags=["runs"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class ScreenedTool(BaseModel):
    """Resultado de tool retirado (ADR-0030); o trecho fica só no banco."""

    tool: str
    rule: str
    term: str | None = None


class AgentRunResponse(BaseModel):
    id: UUID
    agent_config_id: UUID
    user_id: str
    run_id: str | None
    status: str
    duration_ms: int | None
    error: str | None
    blocked_by: str | None = None
    screened_tools: list[ScreenedTool] = []
    # run encerrado antes do fim sem ser erro, ex.: run_cost_limit (ADR-0031)
    stop_reason: str | None = None
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
    """Dias de um período como `30d`; o formato já vem conferido pelo pattern da query."""
    return int(period[:-1])


def _to_metrics_response(
    run_metrics: RunMetrics, blocked_by: dict[str, int]
) -> AgentMetricsResponse:
    return AgentMetricsResponse(
        total_runs=run_metrics.total_runs,
        error_rate=run_metrics.error_rate,
        p50_ms=run_metrics.p50_ms,
        p95_ms=run_metrics.p95_ms,
        period_days=run_metrics.period_days,
        blocked_runs=run_metrics.blocked_runs,
        blocked_by=blocked_by,
    )


@router.get("/{config_id}/metrics", response_model=AgentMetricsResponse)
def get_metrics(
    config_id: UUID,
    session: SessionDep,
    period: str = Query(default="30d", pattern=r"^\d+d$"),  # noqa: B008
) -> AgentMetricsResponse:
    """Latência, taxa de erro e bloqueios por regra do agente no período."""
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
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),  # noqa: B008
    status: str | None = Query(  # noqa: B008
        default=None, pattern=r"^(success|error|paused|blocked|cancelled|running)$"
    ),
    since: datetime | None = Query(default=None),  # noqa: B008
    until: datetime | None = Query(default=None),  # noqa: B008
) -> RunsPage:
    """Execuções paginadas do config; quem não é owner vê o usuário mascarado."""
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")

    run_repo = RunRepository(session)
    runs, total = run_repo.list_by_config(
        config_id, page=page, page_size=page_size, status=status, since=since, until=until
    )
    everyone = sees_everyone(request)
    # consumo do workflow é o das etapas, gravado nos agentes e times que rodaram
    # por run_id: (etapas, tokens, custo)
    step_consumption: dict[str, tuple[int | None, int | None, float | None]] = {}
    if config.kind == "workflow":
        consumption_by_run = run_repo.child_consumption([run.run_id for run in runs if run.run_id])
        step_consumption = {
            run.run_id or "": consumption_by_run.get(run.run_id or "", (0, 0, None)) for run in runs
        }
    return RunsPage(
        items=[
            AgentRunResponse(
                id=run.id,
                agent_config_id=run.agent_config_id,
                user_id=run.user_id if everyone else masked_user(run.user_id),
                run_id=run.run_id,
                status=run.status,
                duration_ms=run.duration_ms,
                error=run.error,
                blocked_by=run.blocked_by,
                screened_tools=[
                    ScreenedTool.model_validate(screened) for screened in run.screened_tools or []
                ],
                stop_reason=run.stop_reason,
                steps=step_consumption.get(run.run_id or "", (None, None, None))[0],
                total_tokens=step_consumption.get(run.run_id or "", (None, None, None))[1],
                cost=step_consumption.get(run.run_id or "", (None, None, None))[2],
                created_at=run.created_at,
            )
            for run in runs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
