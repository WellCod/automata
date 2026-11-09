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
    raw = step.get("timeout_at")
    if not raw:
        return False
    try:
        moment = datetime.fromisoformat(str(raw))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment <= now


def expire_reviews(session: Session, now: datetime) -> list[str]:
    """Runs pausados com prazo de revisão vencido viram cancelados; devolve os run_ids."""
    rows = session.scalars(
        select(AgentRun)
        .where(AgentRun.status == "paused", AgentRun.pending_steps.is_not(None))
        .with_for_update(skip_locked=True)
    ).all()
    expired: list[tuple[str, list[dict[str, Any]]]] = []
    for row in rows:
        steps = [s for s in row.pending_steps or [] if _expired(s, now)]
        if steps and row.run_id:
            expired.append((row.run_id, steps))
    repo = RunRepository(session)
    at = now.isoformat()
    for run_id, steps in expired:
        session.execute(
            update(AgentRun)
            .where(AgentRun.run_id == run_id, AgentRun.status == "paused")
            .values(status="cancelled", stop_reason=STOP_REVIEW_TIMEOUT, pending_steps=None)
        )
        repo.append_reviews(
            run_id,
            [
                {
                    "step_id": str(s.get("step_id")),
                    "step_name": s.get("step_name"),
                    "decision": "timeout",
                    "by": "prazo",
                    "at": at,
                }
                for s in steps
            ],
        )
    session.commit()
    if expired:
        logger.info("revisões vencidas canceladas", extra={"count": len(expired)})
    return [run_id for run_id, _ in expired]
