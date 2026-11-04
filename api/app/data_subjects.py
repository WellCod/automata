"""Dados de um titular na instância (ADR-0032): o que há, a cópia e, no PR seguinte, a exclusão.

O titular é o `user_id` do run. As tabelas do Agno ficam no schema `ai`, com os nomes
do próprio `PostgresDb`; tabela que o Agno ainda não criou não tem nada a mostrar.
"""

import gzip
import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any
from uuid import UUID

from sqlalchemy import Table, func, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from sqlalchemy.sql.schema import MetaData

from app.db import get_engine
from app.models.data_subject import DataSubjectRequest
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.settings import get_settings

logger = logging.getLogger(__name__)

EXPORT_TTL = timedelta(days=7)
AGNO_SCHEMA = "ai"
# tabelas do Agno com a coluna user_id, pela chave do nome no PostgresDb
AGNO_BY_USER: dict[str, str] = {
    "sessions": "session_table_name",
    "runs": "runs_table_name",
    "memories": "memory_table_name",
    "approvals": "approvals_table_name",
    "tool_results": "tool_results_table_name",
    "traces": "trace_table_name",
    "jobs": "job_table_name",
    "eval_runs": "eval_table_name",
    "learnings": "learnings_table_name",
    "metrics": "metrics_table_name",
}


def subject_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()


@lru_cache(maxsize=1)
def agno_table_names() -> dict[str, str]:
    from agno.db.postgres import PostgresDb

    # o construtor não conecta: serve só para ler os nomes que o Agno usa
    db = PostgresDb(db_url=get_settings().database_url)
    names = {key: getattr(db, attr) for key, attr in AGNO_BY_USER.items()}
    names["spans"] = db.span_table_name
    names["transcripts"] = db.transcripts_table_name
    names["compactions"] = db.compactions_table_name
    return names


def agno_table(conn: Connection, key: str) -> Table | None:
    name = agno_table_names()[key]
    if not inspect(conn).has_table(name, schema=AGNO_SCHEMA):
        return None
    return Table(name, MetaData(), schema=AGNO_SCHEMA, autoload_with=conn)


def _count(conn: Connection, table: Table | None, column: str, value: Any) -> int:
    if table is None or column not in table.c:
        return 0
    return int(conn.scalar(select(func.count()).where(table.c[column] == value)) or 0)


def inventory(user_id: str) -> dict[str, int]:
    """Quantas linhas de cada lugar são do titular."""
    counts: dict[str, int] = {}
    engine = get_engine()
    with engine.connect() as conn:
        for key in AGNO_BY_USER:
            counts[key] = _count(conn, agno_table(conn, key), "user_id", user_id)
    with Session(engine) as session:
        counts["agent_runs"] = int(
            session.scalar(select(func.count()).where(AgentRun.user_id == user_id)) or 0
        )
        counts["usage_events"] = int(
            session.scalar(select(func.count()).where(UsageEvent.user_id == user_id)) or 0
        )
    return counts


def _rows(
    conn: Connection, table: Table | None, column: str, values: list[Any]
) -> list[dict[str, Any]]:
    if table is None or column not in table.c or not values:
        return []
    return [
        dict(row._mapping) for row in conn.execute(select(table).where(table.c[column].in_(values)))
    ]


def build_export(user_id: str) -> dict[str, Any]:
    """Tudo o que a instância guarda do titular, no formato das tabelas."""
    engine = get_engine()
    data: dict[str, Any] = {
        "user_id": user_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "agno": {},
    }
    with engine.connect() as conn:
        for key in AGNO_BY_USER:
            data["agno"][key] = _rows(conn, agno_table(conn, key), "user_id", [user_id])
        trace_ids = [t["trace_id"] for t in data["agno"]["traces"] if t.get("trace_id")]
        data["agno"]["spans"] = _rows(conn, agno_table(conn, "spans"), "trace_id", trace_ids)
    with Session(engine) as session:
        data["agent_runs"] = [
            {
                "run_id": r.run_id,
                "agent_config_id": str(r.agent_config_id),
                "session_id": r.session_id,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
                "review_log": r.review_log,
                "screened_tools": r.screened_tools,
                "block_detail": r.block_detail,
            }
            for r in session.scalars(select(AgentRun).where(AgentRun.user_id == user_id))
        ]
        data["usage"] = [
            {"period": period, "events": events, "total_tokens": int(tokens or 0), "cost": cost}
            for period, events, tokens, cost in session.execute(
                select(
                    UsageEvent.period,
                    func.count(),
                    func.sum(UsageEvent.total_tokens),
                    func.sum(UsageEvent.cost),
                )
                .where(UsageEvent.user_id == user_id)
                .group_by(UsageEvent.period)
                .order_by(UsageEvent.period)
            )
        ]
    return data


def _finish(request_id: UUID, **values: Any) -> None:
    with Session(get_engine()) as session:
        request = session.get(DataSubjectRequest, request_id)
        if request is None:
            return
        for key, value in values.items():
            setattr(request, key, value)
        request.finished_at = datetime.now(UTC)
        session.commit()


def run_export(request_id: UUID) -> None:
    """Background: gera o arquivo e guarda por 7 dias. Nunca levanta."""
    with Session(get_engine()) as session:
        request = session.get(DataSubjectRequest, request_id)
        if request is None or request.subject is None:
            return
        user_id = request.subject
        request.status = "running"
        session.commit()
    try:
        data = build_export(user_id)
        payload = json.dumps(data, ensure_ascii=False, default=str).encode()
        counts = {key: len(rows) for key, rows in data["agno"].items()}
        counts["agent_runs"] = len(data["agent_runs"])
        counts["usage_periods"] = len(data["usage"])
        _finish(
            request_id,
            status="done",
            counts=counts,
            result=gzip.compress(payload),
            expires_at=datetime.now(UTC) + EXPORT_TTL,
        )
        logger.info("exportação do titular pronta", extra={"request_id": str(request_id)})
    except Exception as exc:
        logger.warning("exportação do titular falhou", extra={"request_id": str(request_id)})
        _finish(request_id, status="failed", error=str(exc)[:500], subject=None)


def purge_expired(session: Session, now: datetime | None = None) -> int:
    """Arquivo vencido sai do banco, e o id em claro com ele."""
    moment = now or datetime.now(UTC)
    expired = session.scalars(
        select(DataSubjectRequest).where(
            DataSubjectRequest.expires_at.is_not(None), DataSubjectRequest.expires_at <= moment
        )
    ).all()
    for request in expired:
        request.result = None
        request.subject = None
        request.expires_at = None
        request.status = "expired"
    if expired:
        session.commit()
    return len(expired)
