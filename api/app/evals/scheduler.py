"""Agendamento da suíte com poller próprio (ADR-0016).

Um laço no lifespan da API acorda a cada minuto, reivindica os agendamentos
vencidos com `FOR UPDATE SKIP LOCKED` e cria a execução pelo mesmo caminho do
botão Rodar (`create_run`), sem HTTP. Com mais de uma réplica, a que travou a
linha cria a execução e as outras pulam. O próximo horário é calculado a partir
de agora: se a API ficou fora do ar, a execução vencida roda uma vez só na volta.

A validação e o cálculo do próximo horário vêm do `agno.scheduler.cron`; o
scheduler do AgentOS não é usado, porque o token interno dele não cobre as
rotas próprias e o vínculo de origem só aceita run de agente, time ou workflow.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from agno.scheduler.cron import compute_next_run, validate_cron_expr, validate_timezone
from sqlalchemy.orm import Session

from app import alerts
from app.db import get_engine
from app.evals.notify import notify_after
from app.evals.runner import execute
from app.evals.service import EvalRunRefused, create_run
from app.models.eval import EvalSchedule
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalScheduleRepository
from app.schemas.eval import EvalRunCreate

logger = logging.getLogger(__name__)

ACTOR = "agendamento"
POLL_SECONDS = 60
MIN_INTERVAL = timedelta(hours=1)
# horários seguidos conferidos contra o intervalo mínimo: cobre dois dias de um cron horário
_SAMPLES = 48


def next_run(cron_expr: str, timezone: str, after: datetime) -> datetime:
    epoch = compute_next_run(cron_expr, timezone, after_epoch=int(after.timestamp()))
    return datetime.fromtimestamp(epoch, tz=UTC)


def validate(cron_expr: str, timezone: str) -> str | None:
    """Motivo da recusa, ou None. Cron vazio (sob demanda no Agno) não vale aqui."""
    if not cron_expr.strip() or not validate_cron_expr(cron_expr):
        return "Expressão cron inválida"
    if not validate_timezone(timezone):
        return f"Fuso horário desconhecido: {timezone}"
    # só entre horários seguidos do cron: de agora até o primeiro pode ser curto
    previous = next_run(cron_expr, timezone, datetime.now(UTC))
    for _ in range(_SAMPLES):
        following = next_run(cron_expr, timezone, previous)
        if following - previous < MIN_INTERVAL:
            return "O intervalo mínimo entre execuções é de 1 hora"
        previous = following
    return None


def _fire(session: Session, schedule: EvalSchedule, now: datetime) -> UUID | None:
    schedule.next_run_at = next_run(schedule.cron_expr, schedule.timezone, now)
    schedule.last_attempt_at = now
    config = ConfigRepository(session).get_config(schedule.agent_config_id)
    if config is None:
        return None
    body = EvalRunCreate.model_validate(
        {"target": schedule.target, "judge_model": schedule.judge_model}
    )
    try:
        run = create_run(session, config, body, actor=ACTOR, trigger="schedule", commit=False)
    except EvalRunRefused as exc:
        # o horário passa; o motivo fica visível na aba Testes
        schedule.last_error = exc.detail
        return None
    schedule.last_run_id = run.id
    schedule.last_error = None
    return run.id


def poll_once(now: datetime | None = None) -> list[UUID]:
    """Cria as execuções vencidas e devolve os ids; quem chama roda o `execute`."""
    now = now or datetime.now(UTC)
    started: list[UUID] = []
    with Session(get_engine()) as session:
        for schedule in EvalScheduleRepository(session).claim_due(now):
            run_id = _fire(session, schedule, now)
            if run_id is not None:
                started.append(run_id)
        # um commit só: as travas valem até aqui, e a execução nasce junto com o próximo horário
        session.commit()
    return started


async def _run_and_notify(run_id: UUID) -> None:
    await execute(run_id)
    # o aviso só sai em mudança de estado e nunca levanta (ADR-0018)
    await asyncio.to_thread(notify_after, run_id)


async def run_forever(poll_seconds: int = POLL_SECONDS) -> None:
    tasks: set[asyncio.Task[None]] = set()
    while True:
        try:
            for run_id in await asyncio.to_thread(poll_once):
                logger.info("suíte agendada iniciada", extra={"eval_run_id": str(run_id)})
                task = asyncio.create_task(_run_and_notify(run_id))
                tasks.add(task)
                task.add_done_callback(tasks.discard)
        except Exception as exc:
            logger.warning("falha no agendamento da suíte", extra={"error": str(exc)})
        # orçamento e pico de erro dos destinos de aviso (ADR-0021), no mesmo minuto
        await asyncio.to_thread(alerts.poll_once)
        await asyncio.sleep(poll_seconds)
