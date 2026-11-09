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
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.agents.memory import memory_db
from app.db import get_engine
from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigPayload, MemorySettings

logger = logging.getLogger(__name__)

PURGE_EVERY_S = 3600.0
_last_purge: float | None = None


def memories(
    agent_id: str | None = None, user_id: str | None = None, *, team_id: str | None = None
) -> list[UserMemory]:
    rows = memory_db().get_user_memories(
        agent_id=agent_id,
        team_id=team_id,
        user_id=user_id,
        sort_by="updated_at",
        sort_order="desc",
    )
    return [m for m in rows if isinstance(m, UserMemory)] if isinstance(rows, list) else []


def delete(memory_ids: list[str], user_id: str | None = None) -> None:
    if memory_ids:
        memory_db().delete_user_memories(memory_ids=memory_ids, user_id=user_id)


def of_config(config_id: str, kind: str, user_id: str | None = None) -> list[UserMemory]:
    """Memórias de um agente (agent_id) ou de um time (team_id), ADR-0035."""
    if kind == "team":
        return memories(user_id=user_id, team_id=config_id)
    return memories(agent_id=config_id, user_id=user_id)


def retention_by_agent(session: Session) -> dict[str, tuple[str, int]]:
    """Tipo e prazo da versão vigente de cada agente e time; sem seção, o padrão."""
    rows = session.execute(
        select(AgentConfig.id, AgentConfig.kind, AgentConfigVersion.payload)
        .join(AgentConfigVersion, AgentConfigVersion.id == AgentConfig.current_version_id)
        .where(AgentConfig.kind.in_(["agent", "team"]))
    ).all()
    out: dict[str, tuple[str, int]] = {}
    for config_id, kind, payload in rows:
        try:
            settings = ConfigPayload.model_validate(payload).memory
        except ValueError:
            settings = MemorySettings()
        out[str(config_id)] = (str(kind), settings.retention_days)
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
    db = memory_db()
    table = f'"{db.db_schema}"."{db.memory_table_name}"'
    # direto na tabela: carregar todas as memórias de cada agente em Python, de hora em
    # hora, crescia com o histórico (Fase 44)
    with get_engine().begin() as conn:
        for config_id, (kind, days) in retention.items():
            column = "team_id" if kind == "team" else "agent_id"
            limit = int((now - timedelta(days=days)).timestamp())
            result = conn.execute(
                text(
                    f"DELETE FROM {table} WHERE {column} = :config_id "
                    "AND COALESCE(updated_at, created_at, 0) < :limit"
                ),
                {"config_id": config_id, "limit": limit},
            )
            removed += int(result.rowcount or 0)
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
