from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.embedding_usage import EmbeddingTotals, EmbeddingUsageRepository
from app.repositories.usage import UsageRepository, UsageRollup

router = APIRouter(
    prefix="/api/v1/usage",
    tags=["usage"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class RollupItem(BaseModel):
    agent_config_id: UUID
    period: str
    run_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float | None
    # buscas do agente em bases de conhecimento, à parte dos tokens do modelo
    embedding_tokens: int = 0
    embedding_cost: float | None = None


def _current_period() -> str:
    """Mês corrente no formato do rollup, `YYYYMM`, em UTC."""
    return datetime.now(UTC).strftime("%Y%m")


def _to_item(rollup: UsageRollup, embedding: EmbeddingTotals | None) -> RollupItem:
    """Consumo do modelo somado ao das buscas em base do mesmo agente."""
    return RollupItem(
        agent_config_id=rollup.agent_config_id,
        period=rollup.period,
        run_count=rollup.run_count,
        input_tokens=rollup.input_tokens,
        output_tokens=rollup.output_tokens,
        total_tokens=rollup.total_tokens,
        cost=rollup.cost,
        embedding_tokens=embedding.tokens if embedding else 0,
        embedding_cost=embedding.cost if embedding else None,
    )


@router.get("/rollup", response_model=list[RollupItem])
def get_rollup(
    session: SessionDep,
    period: str = Query(
        default="",
        description="Período no formato YYYYMM. Vazio = mês corrente.",
        pattern=r"^\d{6}$|^$",
    ),
    agent_id: UUID | None = Query(default=None),  # noqa: B008
) -> list[RollupItem]:
    """Consumo do mês por agente, com o embedding das buscas em base à parte."""
    resolved_period = period or _current_period()
    usage_repo = UsageRepository(session)
    rows = usage_repo.rollup(period=resolved_period, agent_config_id=agent_id)
    embedding_by_agent = EmbeddingUsageRepository(session).by_agent(
        period=resolved_period, agent_config_id=agent_id
    )
    # tira do dicionário o embedding de quem já tem linha; o que sobra vira linha própria
    items = [
        _to_item(rollup, embedding_by_agent.pop(rollup.agent_config_id, None)) for rollup in rows
    ]
    # agente que só buscou em base (run sem consumo registrado) também aparece
    for config_id, totals in embedding_by_agent.items():
        empty = UsageRollup(config_id, resolved_period, 0, 0, 0, 0, None)
        items.append(_to_item(empty, totals))
    return items


_CSV_HEADER = [
    "data",
    "agente",
    "modelo",
    "execucoes",
    "tokens_entrada",
    "tokens_saida",
    "tokens_total",
    "custo_usd",
]


def _cell(value: object) -> str:
    """Valor da célula do CSV, neutralizado contra fórmula."""
    text = "" if value is None else str(value)
    # célula começando com = + - @ vira fórmula no Excel (mesma regra do CSV de casos)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/export", response_class=Response)
def export_usage(
    session: SessionDep,
    period: str = Query(
        default="",
        description="Período no formato YYYYMM. Vazio = mês corrente.",
        pattern=r"^\d{6}$|^$",
    ),
) -> Response:
    """Consumo do mês por dia, agente e modelo, sem o id de quem usou (COM-06)."""
    import csv
    import io

    from sqlalchemy import Date, cast, func, select

    from app.models.config import AgentConfig
    from app.models.usage import UsageEvent

    resolved_period = period or _current_period()
    day = cast(UsageEvent.created_at, Date)
    rows = session.execute(
        select(
            day,
            AgentConfig.name,
            UsageEvent.model_id,
            func.count(func.distinct(UsageEvent.run_id)),
            func.sum(UsageEvent.input_tokens),
            func.sum(UsageEvent.output_tokens),
            func.sum(UsageEvent.total_tokens),
            func.sum(UsageEvent.cost),
        )
        .join(AgentConfig, AgentConfig.id == UsageEvent.agent_config_id)
        .where(UsageEvent.period == resolved_period, UsageEvent.eval_run_id.is_(None))
        .group_by(day, AgentConfig.name, UsageEvent.model_id)
        .order_by(day, AgentConfig.name)
    ).all()
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer, delimiter=";")
    writer.writerow(_CSV_HEADER)
    # colunas na ordem do select: dia, agente, modelo, execuções, três de tokens e custo
    for row in rows:
        cost = "" if row[7] is None else f"{row[7]:.6f}"
        writer.writerow([_cell(row[0]), _cell(row[1]), _cell(row[2]), *row[3:7], cost])
    return Response(
        # BOM: o Excel em português abre o arquivo com acento certo
        content="\ufeff" + csv_buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="consumo-{resolved_period}.csv"'},
    )
