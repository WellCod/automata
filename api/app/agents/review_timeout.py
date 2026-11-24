"""Prazo da revisão humana (ADR-0023) vencendo sem ninguém abrir o run (Fase 44).

O Agno só confere o `timeout_at` quando alguém tenta continuar o run. Sem varredura,
o run vencido ficava pausado para sempre e a pendência seguia em Aprovações. A rodada
do poller marca o run como cancelado, com o motivo e a entrada no registro de revisões.
Se alguém ainda tentar o continue, o Agno aplica o mesmo cancelamento.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.run import AgentRun
from app.repositories.run import RunRepository

logger = logging.getLogger(__name__)

STOP_REVIEW_TIMEOUT = "review_timeout"


def _expired(step: dict[str, Any], now: datetime) -> bool:
    """Se o prazo da etapa pendente já passou; sem prazo ou com data ilegível, não."""
    raw_timeout = step.get("timeout_at")
    if not raw_timeout:
        return False
    try:
        timeout_at = datetime.fromisoformat(str(raw_timeout))
    except ValueError:
        return False
    # data sem fuso vale como UTC, para comparar com o `now` com fuso
    if timeout_at.tzinfo is None:
        timeout_at = timeout_at.replace(tzinfo=UTC)
    return timeout_at <= now


def expire_reviews(session: Session, now: datetime) -> list[str]:
    """Runs pausados com prazo de revisão vencido viram cancelados; devolve os run_ids."""
    # skip locked: duas rodadas do poller (ou duas réplicas) não cancelam o mesmo run
    rows = session.scalars(
        select(AgentRun)
        .where(AgentRun.status == "paused", AgentRun.pending_steps.is_not(None))
        .with_for_update(skip_locked=True)
    ).all()
    expired: list[tuple[str, list[dict[str, Any]]]] = []
    for row in rows:
        expired_steps = [step for step in row.pending_steps or [] if _expired(step, now)]
        if expired_steps and row.run_id:
            expired.append((row.run_id, expired_steps))
    repo = RunRepository(session)
    expired_at = now.isoformat()
    for run_id, expired_steps in expired:
        # o status no WHERE evita cancelar run que alguém continuou entre a leitura e aqui
        session.execute(
            update(AgentRun)
            .where(AgentRun.run_id == run_id, AgentRun.status == "paused")
            .values(status="cancelled", stop_reason=STOP_REVIEW_TIMEOUT, pending_steps=None)
        )
        repo.append_reviews(
            run_id,
            [
                {
                    "step_id": str(step.get("step_id")),
                    "step_name": step.get("step_name"),
                    "decision": "timeout",
                    "by": "prazo",
                    "at": expired_at,
                }
                for step in expired_steps
            ],
        )
    session.commit()
    if expired:
        logger.info("revisões vencidas canceladas", extra={"count": len(expired)})
    return [run_id for run_id, _ in expired]
