from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
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
    return datetime.now(UTC).strftime("%Y%m")


def _to_item(r: UsageRollup, emb: EmbeddingTotals | None) -> RollupItem:
    return RollupItem(
        agent_config_id=r.agent_config_id,
        period=r.period,
        run_count=r.run_count,
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        total_tokens=r.total_tokens,
        cost=r.cost,
        embedding_tokens=emb.tokens if emb else 0,
        embedding_cost=emb.cost if emb else None,
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
    resolved_period = period or _current_period()
    repo = UsageRepository(session)
    rows = repo.rollup(period=resolved_period, agent_config_id=agent_id)
    emb = EmbeddingUsageRepository(session).by_agent(
        period=resolved_period, agent_config_id=agent_id
    )
    items = [_to_item(r, emb.pop(r.agent_config_id, None)) for r in rows]
    # agente que só buscou em base (run sem consumo registrado) também aparece
    for config_id, totals in emb.items():
        empty = UsageRollup(config_id, resolved_period, 0, 0, 0, 0, None)
        items.append(_to_item(empty, totals))
    return items
