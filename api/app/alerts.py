"""Destinos de aviso da instância (ADR-0021).

Cada destino assina eventos e recebe os de todos os configs. A entrega é a do
webhook da suíte (ADR-0018): HMAC, `text` em português e saída pelo filtro de
URL. Orçamento e pico de erro são conferidos pelo poller a cada minuto; a
tabela `alert_sent` guarda o que já foi mandado, com chave única por config,
evento e janela, e é ela que impede duas réplicas de mandar o mesmo aviso.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import budget
from app.db import get_engine
from app.evals import webhook
from app.models.alert import AlertDestination, AlertSent
from app.models.config import AgentConfig
from app.models.run import AgentRun
from app.secrets import SecretsKeyMissing

logger = logging.getLogger(__name__)

BUDGET_WARNING = "budget.warning"
BUDGET_EXCEEDED = "budget.exceeded"
ERRORS_SPIKE = "errors.spike"
SUITE_EVENTS = ("suite.regressed", "suite.failing", "suite.recovered")
EVENTS = (BUDGET_WARNING, BUDGET_EXCEEDED, ERRORS_SPIKE, *SUITE_EVENTS)

SPIKE_WINDOW = timedelta(minutes=15)
SPIKE_MIN_RUNS = 5
SPIKE_ERROR_RATE = 0.5


def _usd(value: float) -> str:
    return f"US$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def destinations_for(session: Session, event: str) -> list[AlertDestination]:
    rows = session.scalars(select(AlertDestination).order_by(AlertDestination.created_at)).all()
    return [d for d in rows if event in d.events]


def broadcast(session: Session, event: str, data: dict[str, Any], text: str) -> int:
    """Manda a todos os destinos do evento; devolve quantos receberam. Nunca levanta."""
    delivered = 0
    body = webhook.body_for(event, data, text)
    for dest in destinations_for(session, event):
        try:
            status = webhook.deliver(webhook.unseal(dest.webhook_encrypted), event, body)
        except SecretsKeyMissing as exc:
            status = f"recusado: {exc}"
        dest.last_status = status
        dest.last_at = datetime.now(UTC)
        delivered += status.startswith("HTTP 2")
    session.commit()
    return delivered


def claim(session: Session, config_id: UUID, event: str, window: str) -> bool:
    """Reserva o aviso da janela; False quando ele já saiu (aqui ou em outra réplica)."""
    inserted = session.execute(
        insert(AlertSent)
        .values(agent_config_id=config_id, event=event, window=window)
        .on_conflict_do_nothing()
        .returning(AlertSent.event)
    ).first()
    session.commit()
    return inserted is not None


def _budget_text(event: str, config: AgentConfig, state: budget.BudgetState) -> str:
    assert state.limit_usd is not None and state.percent is not None
    if event == BUDGET_WARNING:
        return (
            f"Orçamento de {config.name} chegou a {state.percent:.0f}% no mês: "
            f"{_usd(state.spent_usd)} de {_usd(state.limit_usd)}."
        )
    stop = (
        "Os próximos runs ficam barrados até o mês virar ou o limite subir."
        if state.hard_stop
        else "O bloqueio está desligado: o agente continua atendendo."
    )
    return (
        f"Orçamento de {config.name} estourou: {_usd(state.spent_usd)} de "
        f"{_usd(state.limit_usd)} no mês. {stop}"
    )


def check_budgets(session: Session, now: datetime) -> list[tuple[UUID, str]]:
    period = budget.current_period(now)
    sent: list[tuple[UUID, str]] = []
    # lista fechada antes do laço: o claim faz commit no meio
    configs = session.scalars(
        select(AgentConfig).where(AgentConfig.budget_monthly_usd.is_not(None))
    ).all()
    for config in configs:
        state = budget.state_for(config, budget.month_spend(session, config.id, period))
        # estourar direto, sem passar pelo aviso, manda só o estouro
        event = {"warning": BUDGET_WARNING, "exceeded": BUDGET_EXCEEDED}.get(state.level or "")
        if event is None or not destinations_for(session, event):
            continue
        if not claim(session, config.id, event, period):
            continue
        broadcast(
            session,
            event,
            {
                "config_id": str(config.id),
                "config_name": config.name,
                "period": period,
                "spent_usd": round(state.spent_usd, 4),
                "limit_usd": state.limit_usd,
                "percent": round(state.percent or 0, 1),
                "hard_stop": state.hard_stop,
            },
            _budget_text(event, config, state),
        )
        sent.append((config.id, event))
    return sent


@dataclass(frozen=True)
class ErrorRate:
    config_id: UUID
    runs: int
    errors: int


def error_rates(session: Session, now: datetime) -> list[ErrorRate]:
    """Taxa de erro recente por config, só de conversa: bloqueio não é erro e teste fica fora."""
    errors = func.sum(case((AgentRun.status == "error", 1), else_=0))
    rows = session.execute(
        select(AgentRun.agent_config_id, func.count(AgentRun.id), errors)
        .where(
            AgentRun.created_at >= now - SPIKE_WINDOW,
            AgentRun.status.in_(("success", "error")),
            AgentRun.eval_run_id.is_(None),
        )
        .group_by(AgentRun.agent_config_id)
    )
    return [ErrorRate(config_id=c, runs=int(n), errors=int(e or 0)) for c, n, e in rows]


def check_errors(session: Session, now: datetime) -> list[UUID]:
    if not destinations_for(session, ERRORS_SPIKE):
        return []
    sent: list[UUID] = []
    # janela de uma hora: no máximo um aviso de pico por config por hora
    window = now.strftime("%Y%m%d%H")
    for rate in error_rates(session, now):
        if rate.runs < SPIKE_MIN_RUNS or rate.errors / rate.runs < SPIKE_ERROR_RATE:
            continue
        if not claim(session, rate.config_id, ERRORS_SPIKE, window):
            continue
        config = session.get(AgentConfig, rate.config_id)
        name = config.name if config is not None else str(rate.config_id)
        percent = rate.errors / rate.runs * 100
        broadcast(
            session,
            ERRORS_SPIKE,
            {
                "config_id": str(rate.config_id),
                "config_name": name,
                "window_minutes": int(SPIKE_WINDOW.total_seconds() // 60),
                "runs": rate.runs,
                "errors": rate.errors,
            },
            f"Taxa de erro de {name} em {percent:.0f}% nos últimos 15 minutos "
            f"({rate.errors} de {rate.runs} runs).",
        )
        sent.append(rate.config_id)
    return sent


def poll_once(now: datetime | None = None) -> None:
    """Uma rodada do poller: orçamento e pico de erro. Nunca levanta."""
    moment = now or datetime.now(UTC)
    for check in (check_budgets, check_errors):
        try:
            with Session(get_engine()) as session:
                check(session, moment)
        except Exception as exc:
            logger.warning(
                "falha na checagem de avisos", extra={"check": check.__name__, "error": str(exc)}
            )
