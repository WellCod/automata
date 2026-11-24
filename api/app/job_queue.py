"""Fila durável vista pelo owner e retry do agente idempotente (ADR-0037).

Os jobs ficam na tabela do Agno (`ai.agno_jobs`); `component_id` é o id do config,
que é o id com que o agente ou o time é registrado no AgentOS.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from agno.db.postgres import PostgresDb
from agno.db.schemas.jobs import JOB_STATUSES
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigPayload
from app.settings import get_settings

logger = logging.getLogger(__name__)

JOB_FAILED = "job.failed"
# falha mais velha que isso não gera aviso nem retry: o deploy não acorda o histórico
RECENT = timedelta(hours=24)


def jobs_db() -> PostgresDb:
    # mesmo pool da API (OPS-09)
    return PostgresDb(db_engine=get_engine())


def durable() -> bool:
    return get_settings().background_queue_durable


def _when(epoch: Any) -> datetime | None:
    """Época em segundos, como o Agno grava os jobs, em datetime UTC."""
    return datetime.fromtimestamp(int(epoch), UTC) if epoch else None


def config_names(session: Session, ids: set[str]) -> dict[str, str]:
    """Nome de cada config pelo id; id que não é UUID fica de fora."""
    config_uuids = []
    for value in ids:
        try:
            config_uuids.append(UUID(value))
        except ValueError:
            continue
    if not config_uuids:
        return {}
    rows = session.execute(
        select(AgentConfig.id, AgentConfig.name).where(AgentConfig.id.in_(config_uuids))
    )
    return {str(row.id): row.name for row in rows}


def summary(session: Session, limit: int = 50) -> dict[str, Any]:
    """Contagem por status, o job mais antigo na fila e os mais recentes, para o painel."""
    queue_db = jobs_db()
    counts = {status: queue_db.list_jobs(status=status, limit=1)[1] for status in JOB_STATUSES}
    oldest_queued, _ = queue_db.list_jobs(
        status="queued", limit=1, sort_by="created_at", sort_order="asc"
    )
    recent, _ = queue_db.list_jobs(limit=limit, sort_by="created_at", sort_order="desc")
    names = config_names(session, {str(job.get("component_id")) for job in recent})
    return {
        "counts": counts,
        "oldest_queued_at": _when(oldest_queued[0]["created_at"]) if oldest_queued else None,
        "jobs": [
            {
                "id": str(job["id"]),
                "component_type": job.get("component_type"),
                "component_id": job.get("component_id"),
                "component_name": names.get(str(job.get("component_id"))),
                "status": job.get("status"),
                "attempt": int(job.get("attempt") or 0),
                "max_attempts": int(job.get("max_attempts") or 0),
                "error": (job.get("error") or None) and str(job["error"])[:500],
                "user_id": job.get("user_id"),
                "created_at": _when(job.get("created_at")),
                "completed_at": _when(job.get("completed_at")),
            }
            for job in recent
        ],
    }


def requeue(job_id: str) -> bool:
    return jobs_db().requeue_job(job_id)


def retries_by_config(session: Session, ids: set[str]) -> dict[str, int]:
    """`run.background_retries` da versão vigente de cada config (ADR-0037)."""
    config_uuids = []
    for value in ids:
        try:
            config_uuids.append(UUID(value))
        except ValueError:
            continue
    if not config_uuids:
        return {}
    rows = session.execute(
        select(AgentConfig.id, AgentConfigVersion.payload)
        .join(AgentConfigVersion, AgentConfigVersion.id == AgentConfig.current_version_id)
        .where(AgentConfig.id.in_(config_uuids))
    ).all()
    retries: dict[str, int] = {}
    for config_id, payload in rows:
        try:
            retries[str(config_id)] = ConfigPayload.model_validate(payload).run.background_retries
        except ValueError:
            # payload que não valida mais (versão antiga) fica sem retry
            retries[str(config_id)] = 0
    return retries


def check_jobs(session: Session, now: datetime) -> list[tuple[str, str]]:
    """Rodada do poller: repete o job do agente idempotente; falha de vez vira aviso."""
    from app.alerts import broadcast, claim, destinations_for

    if not durable():
        return []
    failed, _ = jobs_db().list_jobs(status="failed", limit=100, sort_by="updated_at")
    cutoff = (now - RECENT).timestamp()
    recent = [
        job
        for job in failed
        if int(job.get("completed_at") or job.get("updated_at") or 0) >= cutoff
    ]
    if not recent:
        return []
    retries = retries_by_config(session, {str(job.get("component_id")) for job in recent})
    names = config_names(session, set(retries))
    handled: list[tuple[str, str]] = []
    for job in recent:
        job_id, config_id = str(job["id"]), str(job.get("component_id"))
        # o requeue do Agno sobe max_attempts; attempt conta as execuções já feitas
        allowed = retries.get(config_id, 0)
        if allowed and int(job.get("attempt") or 1) <= allowed and requeue(job_id):
            logger.info(
                "job repetido pelo retry do agente",
                extra={"job_id": job_id, "config_id": config_id, "attempt": job.get("attempt")},
            )
            handled.append((job_id, "requeued"))
            continue
        if config_id not in names or not destinations_for(session, JOB_FAILED):
            continue
        # um aviso por job; a janela leva o começo do id do job
        if not claim(session, UUID(config_id), JOB_FAILED, job_id[:16]):
            continue
        broadcast(
            session,
            JOB_FAILED,
            {"job_id": job_id, "config_id": config_id, "attempt": job.get("attempt")},
            f"Run em background de {names[config_id]} falhou"
            f"{' depois dos retries' if allowed else ''}: {str(job.get('error') or '')[:200]}",
        )
        handled.append((job_id, JOB_FAILED))
    return handled
