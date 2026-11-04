"""Fila durável vista pelo owner e retry do agente idempotente (ADR-0037).

Os jobs ficam na tabela do Agno (`ai.agno_jobs`); `component_id` é o id do config,
que é o id com que o agente ou o time é registrado no AgentOS.
"""

import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import UUID

from agno.db.postgres import PostgresDb
from agno.db.schemas.jobs import JOB_STATUSES
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigPayload
from app.settings import get_settings

logger = logging.getLogger(__name__)

JOB_FAILED = "job.failed"
# falha mais velha que isso não gera aviso nem retry: o deploy não acorda o histórico
RECENT = timedelta(hours=24)


@lru_cache(maxsize=1)
def _db(db_url: str) -> PostgresDb:
    return PostgresDb(db_url=db_url)


def jobs_db() -> PostgresDb:
    return _db(get_settings().database_url)


def durable() -> bool:
    return get_settings().background_queue_durable


def _when(epoch: Any) -> datetime | None:
    return datetime.fromtimestamp(int(epoch), UTC) if epoch else None


def config_names(session: Session, ids: set[str]) -> dict[str, str]:
    valid = []
    for value in ids:
        try:
            valid.append(UUID(value))
        except ValueError:
            continue
    if not valid:
        return {}
    rows = session.execute(
        select(AgentConfig.id, AgentConfig.name).where(AgentConfig.id.in_(valid))
    )
    return {str(r.id): r.name for r in rows}


def summary(session: Session, limit: int = 50) -> dict[str, Any]:
    db = jobs_db()
    counts = {status: db.list_jobs(status=status, limit=1)[1] for status in JOB_STATUSES}
    queued, _ = db.list_jobs(status="queued", limit=1, sort_by="created_at", sort_order="asc")
    recent, _ = db.list_jobs(limit=limit, sort_by="created_at", sort_order="desc")
    names = config_names(session, {str(j.get("component_id")) for j in recent})
    return {
        "counts": counts,
        "oldest_queued_at": _when(queued[0]["created_at"]) if queued else None,
        "jobs": [
            {
                "id": str(j["id"]),
                "component_type": j.get("component_type"),
                "component_id": j.get("component_id"),
                "component_name": names.get(str(j.get("component_id"))),
                "status": j.get("status"),
                "attempt": int(j.get("attempt") or 0),
                "max_attempts": int(j.get("max_attempts") or 0),
                "error": (j.get("error") or None) and str(j["error"])[:500],
                "user_id": j.get("user_id"),
                "created_at": _when(j.get("created_at")),
                "completed_at": _when(j.get("completed_at")),
            }
            for j in recent
        ],
    }


def requeue(job_id: str) -> bool:
    return jobs_db().requeue_job(job_id)


def retries_by_config(session: Session, ids: set[str]) -> dict[str, int]:
    """`run.background_retries` da versão vigente de cada config (ADR-0037)."""
    valid = []
    for value in ids:
        try:
            valid.append(UUID(value))
        except ValueError:
            continue
    if not valid:
        return {}
    rows = session.execute(
        select(AgentConfig.id, AgentConfigVersion.payload)
        .join(AgentConfigVersion, AgentConfigVersion.id == AgentConfig.current_version_id)
        .where(AgentConfig.id.in_(valid))
    ).all()
    out: dict[str, int] = {}
    for config_id, payload in rows:
        try:
            out[str(config_id)] = ConfigPayload.model_validate(payload).run.background_retries
        except ValueError:
            out[str(config_id)] = 0
    return out


def check_jobs(session: Session, now: datetime) -> list[tuple[str, str]]:
    """Rodada do poller: repete o job do agente idempotente; falha de vez vira aviso."""
    from app.alerts import broadcast, claim, destinations_for

    if not durable():
        return []
    failed, _ = jobs_db().list_jobs(status="failed", limit=100, sort_by="updated_at")
    cutoff = (now - RECENT).timestamp()
    recent = [j for j in failed if int(j.get("completed_at") or j.get("updated_at") or 0) >= cutoff]
    if not recent:
        return []
    retries = retries_by_config(session, {str(j.get("component_id")) for j in recent})
    names = config_names(session, set(retries))
    done: list[tuple[str, str]] = []
    for job in recent:
        job_id, config_id = str(job["id"]), str(job.get("component_id"))
        allowed = retries.get(config_id, 0)
        if allowed and int(job.get("attempt") or 1) <= allowed and requeue(job_id):
            logger.info(
                "job repetido pelo retry do agente",
                extra={"job_id": job_id, "config_id": config_id, "attempt": job.get("attempt")},
            )
            done.append((job_id, "requeued"))
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
        done.append((job_id, JOB_FAILED))
    return done
