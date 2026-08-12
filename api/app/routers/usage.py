from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.db import SessionDep
from app.repositories.usage import UsageRepository, UsageRollup

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


class RollupItem(BaseModel):
    agent_config_id: UUID
    period: str
    run_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float | None


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y%m")


def _to_item(r: UsageRollup) -> RollupItem:
    return RollupItem(
        agent_config_id=r.agent_config_id,
        period=r.period,
        run_count=r.run_count,
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        total_tokens=r.total_tokens,
        cost=r.cost,
    )


@router.get("/rollup", response_model=list[RollupItem])
def get_rollup(
    period: str = Query(
        default="",
        description="Período no formato YYYYMM. Vazio = mês corrente.",
        pattern=r"^\d{6}$|^$",
    ),
    agent_id: UUID | None = Query(default=None),  # noqa: B008
    session: SessionDep,
) -> list[RollupItem]:
    resolved_period = period or _current_period()
    repo = UsageRepository(session)
    rows = repo.rollup(period=resolved_period, agent_config_id=agent_id)
    return [_to_item(r) for r in rows]
