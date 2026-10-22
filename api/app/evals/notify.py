"""Aviso da suíte agendada nas mudanças de estado (ADR-0018).

Depois de cada execução agendada, compara com a agendada anterior e só avisa
quando o estado muda: suíte quebrada há dias não manda uma mensagem por horário.
O mesmo evento vai ao webhook do agendamento e aos destinos de aviso da
instância que o assinam (ADR-0021).
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import alerts
from app.db import get_engine
from app.evals import webhook
from app.evals.compare import compare
from app.models.config import AgentConfig
from app.models.eval import EvalRun
from app.repositories.eval import EvalRunRepository, EvalScheduleRepository
from app.secrets import SecretsKeyMissing

logger = logging.getLogger(__name__)


def green(run: EvalRun) -> bool:
    # mesma régua do verdict e do gate: não avaliado não conta como aprovado
    return run.status == "completed" and run.total > 0 and run.passed == run.total


def transition(previous: EvalRun | None, current: EvalRun, regressions: list[str]) -> str | None:
    """Evento a mandar, ou None quando o estado não mudou."""
    if green(current):
        return "suite.recovered" if previous is not None and not green(previous) else None
    if previous is None or not green(previous):
        # primeira agendada já falhando avisa; falha seguida de falha, não
        return "suite.failing" if previous is None else None
    return "suite.regressed" if regressions else "suite.failing"


def _previous(session: Session, run: EvalRun) -> EvalRun | None:
    stmt = (
        select(EvalRun)
        .where(
            EvalRun.agent_config_id == run.agent_config_id,
            EvalRun.trigger == "schedule",
            EvalRun.status.in_(("completed", "failed")),
            EvalRun.created_at < run.created_at,
        )
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _text(event: str, name: str, run: EvalRun, regressions: list[str]) -> str:
    score = f"{run.passed} de {run.total} casos passaram"
    if event == "suite.regressed":
        cases = ", ".join(regressions[:5]) + ("…" if len(regressions) > 5 else "")
        return (
            f"Suíte de {name} regrediu: {len(regressions)} caso(s) que passavam "
            f"falharam ({cases}). {score}."
        )
    if event == "suite.recovered":
        return f"Suíte de {name} voltou a passar: {score}."
    if run.status == "failed":
        return f"Suíte de {name} não terminou: {run.error or 'erro na execução'}."
    return f"Suíte de {name} está falhando: {score}."


def notify_after(run_id: UUID) -> str | None:
    """Avisa se a execução agendada mudou o estado; devolve o evento mandado. Nunca levanta."""
    try:
        return _notify(run_id)
    except Exception as exc:
        logger.warning(
            "aviso da suíte falhou", extra={"eval_run_id": str(run_id), "error": str(exc)}
        )
        return None


def _notify(run_id: UUID) -> str | None:
    with Session(get_engine()) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.trigger != "schedule":
            return None
        schedule = EvalScheduleRepository(session).get(run.agent_config_id)
        if schedule is None:
            return None
        previous = _previous(session, run)
        regressions: list[str] = []
        if previous is not None and previous.status == "completed" and run.status == "completed":
            changes = compare(EvalRunRepository(session), previous, run)
            regressions = [c.case_name for c in changes if c.change == "regression"]
        event = transition(previous, run, regressions)
        if event is None:
            return None
        config = session.get(AgentConfig, run.agent_config_id)
        name = config.name if config is not None else str(run.agent_config_id)
        data = {
            "config_id": str(run.agent_config_id),
            "config_name": name,
            "run_id": str(run.id),
            "previous_run_id": str(previous.id) if previous is not None else None,
            "passed": run.passed,
            "total": run.total,
            "regressions": regressions,
        }
        text = _text(event, name, run, regressions)
        sent = alerts.broadcast(session, event, data, text) > 0
        if schedule.webhook_encrypted is not None:
            try:
                target = webhook.unseal(schedule.webhook_encrypted)
                status = webhook.deliver(target, event, webhook.body_for(event, data, text))
                sent = True
            except SecretsKeyMissing as exc:
                status = f"recusado: {exc}"
            schedule.webhook_last_status = status
            schedule.webhook_last_at = datetime.now(UTC)
            session.commit()
        return event if sent else None
