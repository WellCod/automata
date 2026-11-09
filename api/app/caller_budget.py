"""Orçamento mensal por quem chama (ADR-0031).

Quem chama é o `user_id` do run, o mesmo do `usage_event`: o id do usuário do
painel ou `integration:<id>` do token. O gasto do mês soma todos os agentes. Com
bloqueio ligado, um pre-hook barra o run como `budget_exceeded` (`scope: caller`)
antes de chamar o modelo; o aviso sai pelos destinos de alerta da instância.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from agno.exceptions import CheckTrigger, InputCheckError
from agno.run import RunContext
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.budget import CACHE_S, RULE_BUDGET, current_period
from app.db import get_engine
from app.guardrails.input import AnyInput, BlockLog, _block, _Guardrail
from app.models.caller_budget import CallerBudget
from app.models.usage import UsageEvent

logger = logging.getLogger(__name__)

CALLER_BUDGET_MESSAGE = (
    "O orçamento de uso deste mês para o seu acesso acabou. Fale com quem administra "
    "a instância para aumentar o limite."
)
CALLER_WARNING = "caller_budget.warning"
CALLER_EXCEEDED = "caller_budget.exceeded"

_spend: dict[str, tuple[float, float]] = {}
_budgets: dict[str, tuple[float, CallerBudget | None]] = {}


def _keys(subject: str) -> list[str]:
    """O id e o pseudônimo que a exclusão do titular deixa no lugar dele (Fase 43)."""
    from app.data_subjects import pseudonym

    if subject.startswith("apagado:"):
        return [subject]
    return [subject, pseudonym(subject)]


def month_spend(session: Session, subject: str, period: str | None = None) -> float:
    total = session.scalar(
        select(func.coalesce(func.sum(UsageEvent.cost), 0)).where(
            UsageEvent.user_id.in_(_keys(subject)),
            UsageEvent.period == (period or current_period()),
        )
    )
    return float(total or 0)


def _cached_budget(subject: str) -> CallerBudget | None:
    hit = _budgets.get(subject)
    if hit is not None and monotonic() - hit[0] < CACHE_S:
        return hit[1]
    with Session(get_engine()) as session:
        budget = None
        for key in _keys(subject):
            budget = session.get(CallerBudget, key)
            if budget is not None:
                break
        if budget is not None:
            session.expunge(budget)
    _budgets[subject] = (monotonic(), budget)
    return budget


def _cached_spend(subject: str) -> float:
    hit = _spend.get(subject)
    if hit is not None and monotonic() - hit[0] < CACHE_S:
        return hit[1]
    with Session(get_engine()) as session:
        spent = month_spend(session, subject)
    _spend[subject] = (monotonic(), spent)
    return spent


def forget(subject: str) -> None:
    """Orçamento alterado: o próximo run lê de novo."""
    _budgets.pop(subject, None)
    _spend.pop(subject, None)


@dataclass(frozen=True)
class CallerState:
    spent_usd: float
    limit_usd: float
    percent: float
    level: str  # ok, warning, exceeded


def state_for(budget: CallerBudget, spent: float) -> CallerState:
    limit = float(budget.monthly_usd)
    percent = spent / limit * 100 if limit > 0 else 100.0
    level = "exceeded" if percent >= 100 else "warning" if percent >= budget.warn_percent else "ok"
    return CallerState(spent, limit, percent, level)


class CallerBudgetGuardrail(_Guardrail):
    """Pre-hook antes dos guardrails, junto do orçamento do agente (ADR-0021)."""

    def __init__(self, log: BlockLog | None = None) -> None:
        super().__init__(CALLER_BUDGET_MESSAGE, log)

    def _verdict(self, subject: str | None) -> None:
        if not subject:
            return
        budget = _cached_budget(subject)
        if budget is None or not budget.hard_stop:
            return
        spent = _cached_spend(subject)
        if spent >= float(budget.monthly_usd):
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_BUDGET,
                scope="caller",
                spent_usd=round(spent, 4),
                limit_usd=float(budget.monthly_usd),
            )

    def _guarded(self, subject: str | None) -> None:
        try:
            self._verdict(subject)
        except InputCheckError as exc:
            self._note(exc)
            raise

    def check(self, run_input: AnyInput, run_context: RunContext | None = None) -> None:
        self._guarded(run_context.user_id if run_context else None)

    async def async_check(self, run_input: AnyInput, run_context: RunContext | None = None) -> None:
        subject = run_context.user_id if run_context else None
        await asyncio.to_thread(self._guarded, subject)


def _claim(session: Session, subject: str, column: str, period: str) -> bool:
    """Marca o aviso do mês na própria linha; False quando ele já saiu."""
    field = getattr(CallerBudget, column)
    updated = session.execute(
        update(CallerBudget)
        .where(CallerBudget.subject == subject, (field.is_(None)) | (field != period))
        .values({column: period})
    )
    session.commit()
    return bool(getattr(updated, "rowcount", 0))


def check_caller_budgets(session: Session, now: datetime) -> list[tuple[str, str]]:
    """Rodada do poller de avisos (ADR-0021): um aviso e um estouro por mês."""
    from app.alerts import broadcast, destinations_for

    period = current_period(now)
    sent: list[tuple[str, str]] = []
    budgets = session.scalars(select(CallerBudget)).all()
    for budget in budgets:
        state = state_for(budget, month_spend(session, budget.subject, period))
        event = {"warning": CALLER_WARNING, "exceeded": CALLER_EXCEEDED}.get(state.level)
        if event is None or not destinations_for(session, event):
            continue
        column = "warned_period" if event == CALLER_WARNING else "exceeded_period"
        if not _claim(session, budget.subject, column, period):
            continue
        verb = "passou do" if event == CALLER_EXCEEDED else "chegou a"
        broadcast(
            session,
            event,
            {
                "subject": budget.subject,
                "period": period,
                "spent_usd": round(state.spent_usd, 4),
                "limit_usd": state.limit_usd,
                "percent": round(state.percent, 1),
                "hard_stop": budget.hard_stop,
            },
            f"O gasto de {budget.subject} {verb} {round(state.percent)}% do orçamento do mês "
            f"(US$ {state.spent_usd:.2f} de US$ {state.limit_usd:.2f}).",
        )
        sent.append((budget.subject, event))
    return sent
