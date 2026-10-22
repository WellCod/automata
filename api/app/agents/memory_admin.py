"""Ver, apagar e vencer memórias do usuário (ADR-0025).

As memórias ficam na tabela do Agno. A retenção é a da versão vigente de cada
agente e vale também com a memória desligada depois: o que foi guardado fica
até vencer ou até alguém apagar.
"""

import logging
from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import UUID

from agno.db.schemas.memory import UserMemory
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.memory import memory_db
from app.db import get_engine
from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigPayload, MemorySettings

logger = logging.getLogger(__name__)

PURGE_EVERY_S = 3600.0
_last_purge: float | None = None


def memories(agent_id: str | None = None, user_id: str | None = None) -> list[UserMemory]:
    rows = memory_db().get_user_memories(
        agent_id=agent_id, user_id=user_id, sort_by="updated_at", sort_order="desc"
    )
    return [m for m in rows if isinstance(m, UserMemory)] if isinstance(rows, list) else []


def delete(memory_ids: list[str], user_id: str | None = None) -> None:
    if memory_ids:
        memory_db().delete_user_memories(memory_ids=memory_ids, user_id=user_id)


def retention_by_agent(session: Session) -> dict[str, int]:
    """Prazo da versão vigente de cada agente; sem seção, o padrão."""
    rows = session.execute(
        select(AgentConfig.id, AgentConfigVersion.payload)
        .join(AgentConfigVersion, AgentConfigVersion.id == AgentConfig.current_version_id)
        .where(AgentConfig.kind == "agent")
    ).all()
    out: dict[str, int] = {}
    for config_id, payload in rows:
        try:
            settings = ConfigPayload.model_validate(payload).memory
        except ValueError:
            settings = MemorySettings()
        out[str(config_id)] = settings.retention_days
    return out


def expired(rows: list[UserMemory], days: int, now: datetime) -> list[str]:
    limit = (now - timedelta(days=days)).timestamp()
    return [
        m.memory_id for m in rows if m.memory_id and (m.updated_at or m.created_at or 0) < limit
    ]


def purge_expired(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    with Session(get_engine()) as session:
        retention = retention_by_agent(session)
    removed = 0
    for agent_id, days in retention.items():
        ids = expired(memories(agent_id=agent_id), days, now)
        delete(ids)
        removed += len(ids)
    if removed:
        logger.info("memórias vencidas apagadas", extra={"count": removed})
    return removed


def purge_if_due() -> int:
    """Chamado pelo poller a cada minuto; limpa de hora em hora. Nunca levanta."""
    global _last_purge
    if _last_purge is not None and monotonic() - _last_purge < PURGE_EVERY_S:
        return 0
    _last_purge = monotonic()
    try:
        return purge_expired()
    except Exception as exc:
        logger.warning("falha ao vencer memórias", extra={"error": str(exc)})
        return 0


def agent_name_map(session: Session, ids: set[str]) -> dict[str, str]:
    valid = []
    for i in ids:
        try:
            valid.append(UUID(i))
        except ValueError:
            continue
    rows = session.execute(
        select(AgentConfig.id, AgentConfig.name).where(AgentConfig.id.in_(valid))
    )
    return {str(r.id): r.name for r in rows}
