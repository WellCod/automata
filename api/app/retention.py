"""Retenção de conversas por instância (ADR-0045, COM-03).

Com `CONVERSATION_RETENTION_DAYS` acima de zero, a rodada diária do poller apaga o que
passou do prazo: sessões do Agno com runs, transcrições e compactações (na ordem do
`delete_session`, como a exclusão do titular), traces com spans, aprovações, resultados
de tool guardados e mensagens de canal. `agent_run` e `usage_event` ficam para as
métricas e o custo, com `EXPIRED_USER` no lugar do id de quem falou e sem o conteúdo
que o run guardava.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.data_subjects import _affected, agno_table
from app.db import get_engine
from app.models.channel import ChannelConversation, ChannelMessage
from app.models.run import AgentRun
from app.models.usage import UsageEvent

logger = logging.getLogger(__name__)

# no lugar do id de quem falou, em run e consumo que passaram do prazo
EXPIRED_USER = "retencao-expirada"


def _delete_in(conn: Connection, table: Table | None, column: str, values: list[Any]) -> int:
    if table is None or column not in table.c or not values:
        return 0
    return int(conn.execute(table.delete().where(table.c[column].in_(values))).rowcount or 0)


def _older(table: Table, column: str, cutoff: datetime) -> Any:
    # o Agno grava época em segundos nas sessões e ISO 8601 em UTC nos traces
    if str(table.c[column].type).upper().startswith("BIGINT"):
        return table.c[column] < int(cutoff.timestamp())
    return table.c[column] < cutoff.isoformat()


def purge(now: datetime, days: int) -> dict[str, int]:
    """Apaga o que passou de `days` dias; devolve quantas linhas saíram ou mudaram."""
    cutoff = now - timedelta(days=days)
    counts: dict[str, int] = {}
    engine = get_engine()
    with engine.begin() as conn:
        sessions = agno_table(conn, "sessions")
        session_ids: list[Any] = []
        if sessions is not None:
            last = func.coalesce(sessions.c.updated_at, sessions.c.created_at)
            session_ids = list(
                conn.scalars(select(sessions.c.session_id).where(last < int(cutoff.timestamp())))
            )
        for key in ("transcripts", "compactions", "runs", "approvals", "tool_results"):
            counts[key] = _delete_in(conn, agno_table(conn, key), "session_id", session_ids)
        counts["sessions"] = _delete_in(conn, sessions, "session_id", session_ids)

        traces = agno_table(conn, "traces")
        trace_ids: list[Any] = []
        if traces is not None and "created_at" in traces.c:
            trace_ids = list(
                conn.scalars(select(traces.c.trace_id).where(_older(traces, "created_at", cutoff)))
            )
        counts["spans"] = _delete_in(conn, agno_table(conn, "spans"), "trace_id", trace_ids)
        counts["traces"] = _delete_in(conn, traces, "trace_id", trace_ids)

    with Session(engine) as session:
        counts["agent_runs"] = _affected(
            session.execute(
                update(AgentRun)
                .where(AgentRun.created_at < cutoff, AgentRun.user_id != EXPIRED_USER)
                .values(
                    user_id=EXPIRED_USER,
                    error=None,
                    pending_tools=None,
                    pending_steps=None,
                    review_log=None,
                    screened_tools=None,
                    block_detail=None,
                )
            )
        )
        counts["usage_events"] = _affected(
            session.execute(
                update(UsageEvent)
                .where(UsageEvent.created_at < cutoff, UsageEvent.user_id != EXPIRED_USER)
                .values(user_id=EXPIRED_USER)
            )
        )
        counts["channel_messages"] = _affected(
            session.execute(delete(ChannelMessage).where(ChannelMessage.created_at < cutoff))
        )
        # conversa sem mensagem e parada há mais que o prazo some junto com o número
        empty = (
            ~select(ChannelMessage.id)
            .where(ChannelMessage.conversation_id == ChannelConversation.id)
            .exists()
        )
        counts["channel_conversations"] = _affected(
            session.execute(
                delete(ChannelConversation).where(
                    ChannelConversation.last_message_at < cutoff, empty
                )
            )
        )
        session.commit()
    return counts


_last_run: date | None = None


def check_retention(session: Session, now: datetime) -> None:
    """Checagem da rodada do poller de avisos (`alerts.poll_once`)."""
    purge_daily(now)


def purge_daily(now: datetime | None = None) -> dict[str, int]:
    """Uma vez por dia em cada processo; os DELETE são idempotentes entre réplicas."""
    global _last_run
    from app.settings import get_settings

    days = get_settings().conversation_retention_days
    now = now or datetime.now(UTC)
    if days <= 0 or _last_run == now.date():
        return {}
    _last_run = now.date()
    counts = purge(now, days)
    if any(counts.values()):
        logger.info("retenção de conversas aplicada", extra={"days": days, **counts})
    return counts
