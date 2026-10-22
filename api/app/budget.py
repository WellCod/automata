"""Orçamento mensal por config (ADR-0021).

O gasto do mês é a soma do `usage_event` do config no período corrente, com
testes e HyDE, porque é tudo gasto real. Com bloqueio ligado, um hook antes dos
guardrails barra o run como `blocked` (`budget_exceeded`) sem chamar o modelo.
A checagem é antes do run: um run longo pode passar um pouco do limite, e o
bloqueio vale do seguinte em diante.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Literal
from uuid import UUID

from agno.exceptions import CheckTrigger
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.guardrails.input import AnyInput, BlockLog, _block, _Guardrail
from app.models.config import AgentConfig
from app.models.usage import UsageEvent

RULE_BUDGET = "budget_exceeded"
BUDGET_MESSAGE = (
    "O orçamento deste agente para o mês acabou. Fale com quem administra o agente "
    "para aumentar o limite."
)
CACHE_S = 30.0

Level = Literal["ok", "warning", "exceeded"]

_cache: dict[UUID, tuple[float, float]] = {}


def current_period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y%m")


def month_spend(session: Session, config_id: UUID, period: str | None = None) -> float:
    total = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.cost), 0)).where(
            UsageEvent.agent_config_id == config_id,
            UsageEvent.period == (period or current_period()),
        )
    )
    return float(total or 0)


def cached_spend(config_id: UUID) -> float:
    # um run por mensagem consultaria o banco a cada turno; 30 s bastam para barrar
    hit = _cache.get(config_id)
    if hit is not None and monotonic() - hit[0] < CACHE_S:
        return hit[1]
    with Session(get_engine()) as session:
        spent = month_spend(session, config_id)
    _cache[config_id] = (monotonic(), spent)
    return spent


def forget(config_id: UUID) -> None:
    """Limite alterado: o próximo run lê o gasto de novo."""
    _cache.pop(config_id, None)


@dataclass(frozen=True)
class BudgetState:
    limit_usd: float | None
    spent_usd: float
    alert_percent: int
    hard_stop: bool
    # gasto sobre o limite, em %; None sem orçamento
    percent: float | None
    level: Level | None


def state_for(config: AgentConfig, spent: float) -> BudgetState:
    limit = float(config.budget_monthly_usd) if config.budget_monthly_usd is not None else None
    percent: float | None = None
    level: Level | None = None
    if limit is not None:
        percent = spent / limit * 100 if limit > 0 else 100.0
        if percent >= 100:
            level = "exceeded"
        elif percent >= config.budget_alert_percent:
            level = "warning"
        else:
            level = "ok"
    return BudgetState(
        limit_usd=limit,
        spent_usd=spent,
        alert_percent=config.budget_alert_percent,
        hard_stop=config.budget_hard_stop,
        percent=percent,
        level=level,
    )


def hard_limit(config: AgentConfig) -> float | None:
    """Limite que barra o run; None quando não há orçamento ou o bloqueio está desligado."""
    if not config.budget_hard_stop or config.budget_monthly_usd is None:
        return None
    return float(config.budget_monthly_usd)


class BudgetGuardrail(_Guardrail):
    def __init__(self, config_id: UUID, limit_usd: float, log: BlockLog | None = None) -> None:
        super().__init__(BUDGET_MESSAGE, log)
        self.config_id = config_id
        self.limit_usd = limit_usd

    def _verdict(self, spent: float) -> None:
        if spent >= self.limit_usd:
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_BUDGET,
                spent_usd=round(spent, 4),
                limit_usd=self.limit_usd,
            )

    def _check(self, run_input: AnyInput) -> None:
        self._verdict(cached_spend(self.config_id))

    async def _acheck(self, run_input: AnyInput) -> None:
        self._verdict(await asyncio.to_thread(cached_spend, self.config_id))
