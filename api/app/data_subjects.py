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

from sqlalchemy import Table, delete, func, inspect, select, update
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
    # métricas diárias por usuário do Agno 3.2 (painel do AgentOS): também são do titular
    "aggregate_metrics": "aggregate_metrics_table_name",
    "component_metrics": "component_metrics_table_name",
}


def subject_hash(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()


@lru_cache(maxsize=1)
def agno_table_names() -> dict[str, str]:
    """Nome de cada tabela do Agno, lido do próprio `PostgresDb` para seguir a versão instalada."""
    from agno.db.postgres import PostgresDb

    # o construtor não conecta: serve só para ler os nomes que o Agno usa
    db = PostgresDb(db_engine=get_engine())
    names = {key: getattr(db, attr) for key, attr in AGNO_BY_USER.items()}
    names["spans"] = db.span_table_name
    names["transcripts"] = db.transcripts_table_name
    names["compactions"] = db.compactions_table_name
    return names


def agno_table(conn: Connection, key: str) -> Table | None:
    """Tabela do Agno refletida do banco; None quando o Agno ainda não a criou."""
    name = agno_table_names()[key]
    if not inspect(conn).has_table(name, schema=AGNO_SCHEMA):
        return None
    return Table(name, MetaData(), schema=AGNO_SCHEMA, autoload_with=conn)


def _count(conn: Connection, table: Table | None, column: str, value: Any) -> int:
    """Linhas com `column` igual a `value`; tabela ou coluna ausente conta zero."""
    if table is None or column not in table.c:
        return 0
    return int(conn.scalar(select(func.count()).where(table.c[column] == value)) or 0)


def _subject_session_ids(conn: Connection, user_id: str) -> list[Any]:
    """Sessões do titular no Agno.

    Transcrições e compactações não têm `user_id`: são da pessoa por pertencerem a uma
    sessão dela. Consulta, exportação e exclusão usam a mesma lista.
    """
    sessions = agno_table(conn, "sessions")
    if sessions is None:
        return []
    return list(conn.scalars(select(sessions.c.session_id).where(sessions.c.user_id == user_id)))


def _count_in(conn: Connection, table: Table | None, column: str, values: list[Any]) -> int:
    """Linhas com `column` em `values`; tabela ou coluna ausente, ou lista vazia, conta zero."""
    if table is None or column not in table.c or not values:
        return 0
    return int(conn.scalar(select(func.count()).where(table.c[column].in_(values))) or 0)


def inventory(user_id: str) -> dict[str, int]:
    """Quantas linhas de cada lugar são do titular."""
    counts: dict[str, int] = {}
    engine = get_engine()
    with engine.connect() as conn:
        for key in AGNO_BY_USER:
            counts[key] = _count(conn, agno_table(conn, key), "user_id", user_id)
        session_ids = _subject_session_ids(conn, user_id)
        for key in ("transcripts", "compactions"):
            counts[key] = _count_in(conn, agno_table(conn, key), "session_id", session_ids)
    with Session(engine) as session:
        counts["agent_runs"] = int(
            session.scalar(select(func.count()).where(AgentRun.user_id == user_id)) or 0
        )
        counts["usage_events"] = int(
            session.scalar(select(func.count()).where(UsageEvent.user_id == user_id)) or 0
        )
        from app.channels import subject as channel_subject

        counts["channel_messages"] = channel_subject.count(session, user_id)
    return counts


def _rows(
    conn: Connection, table: Table | None, column: str, values: list[Any]
) -> list[dict[str, Any]]:
    """Linhas inteiras com `column` em `values`, como dicionário."""
    if table is None or column not in table.c or not values:
        return []
    return [
        dict(row._mapping) for row in conn.execute(select(table).where(table.c[column].in_(values)))
    ]


def build_export(user_id: str) -> dict[str, Any]:
    """Tudo o que a instância guarda do titular, no formato das tabelas."""
    engine = get_engine()
    export_data: dict[str, Any] = {
        "user_id": user_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "agno": {},
    }
    with engine.connect() as conn:
        for key in AGNO_BY_USER:
            export_data["agno"][key] = _rows(conn, agno_table(conn, key), "user_id", [user_id])
        # span não tem user_id: vem pelos traces do titular
        trace_ids = [
            trace["trace_id"] for trace in export_data["agno"]["traces"] if trace.get("trace_id")
        ]
        export_data["agno"]["spans"] = _rows(conn, agno_table(conn, "spans"), "trace_id", trace_ids)
        # o resumo da compactação e a transcrição são a conversa dela, guardados por sessão
        session_ids = _subject_session_ids(conn, user_id)
        for key in ("transcripts", "compactions"):
            export_data["agno"][key] = _rows(conn, agno_table(conn, key), "session_id", session_ids)
    with Session(engine) as session:
        export_data["agent_runs"] = [
            {
                "run_id": run.run_id,
                "agent_config_id": str(run.agent_config_id),
                "session_id": run.session_id,
                "status": run.status,
                "created_at": run.created_at.isoformat(),
                "review_log": run.review_log,
                "screened_tools": run.screened_tools,
                "block_detail": run.block_detail,
                "pending_tools": run.pending_tools,
                "pending_steps": run.pending_steps,
                "error": run.error,
            }
            for run in session.scalars(select(AgentRun).where(AgentRun.user_id == user_id))
        ]
        export_data["usage"] = [
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
        from app.channels import subject as channel_subject

        # conversas do WhatsApp e do Slack (ADR-0044)
        export_data["channel_conversations"] = channel_subject.export(session, user_id)
    return export_data


def _finish(request_id: UUID, **values: Any) -> None:
    """Grava os campos dados no pedido e a hora do fim; pedido já apagado é ignorado."""
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
        if request is None:
            return
        if request.subject is None:
            # a exclusão do mesmo titular chegou antes: não há o que exportar (Fase 43)
            request.status = "expired"
            request.finished_at = datetime.now(UTC)
            session.commit()
            return
        user_id = request.subject
        request.status = "running"
        session.commit()
    try:
        export_data = build_export(user_id)
        payload = json.dumps(export_data, ensure_ascii=False, default=str).encode()
        counts = {key: len(rows) for key, rows in export_data["agno"].items()}
        counts["agent_runs"] = len(export_data["agent_runs"])
        counts["usage_periods"] = len(export_data["usage"])
        with Session(get_engine()) as session:
            # só grava se a exclusão não zerou o pedido enquanto o arquivo era montado
            stored = session.execute(
                update(DataSubjectRequest)
                .where(
                    DataSubjectRequest.id == request_id,
                    DataSubjectRequest.subject.is_not(None),
                )
                .values(
                    status="done",
                    counts=counts,
                    result=gzip.compress(payload),
                    expires_at=datetime.now(UTC) + EXPORT_TTL,
                    finished_at=datetime.now(UTC),
                )
            )
            session.commit()
        if _affected(stored):
            logger.info("exportação do titular pronta", extra={"request_id": str(request_id)})
        else:
            _finish(request_id, status="expired")
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


def pseudonym(user_id: str) -> str:
    """O id que fica no consumo e nos runs depois da exclusão: conta, mas não identifica."""
    return f"apagado:{subject_hash(user_id)[:16]}"


def _affected(result: Any) -> int:
    """Linhas atingidas por um UPDATE ou DELETE."""
    return int(getattr(result, "rowcount", 0) or 0)


def _delete(conn: Connection, table: Table | None, column: str, values: list[Any]) -> int:
    """Apaga as linhas com `column` em `values`; tabela ou coluna ausente conta zero."""
    if table is None or column not in table.c or not values:
        return 0
    return int(conn.execute(table.delete().where(table.c[column].in_(values))).rowcount or 0)


def erase(user_id: str) -> dict[str, int]:
    """Apaga o titular numa transação; devolve quantas linhas saíram ou mudaram de cada lugar.

    A conversa sai na ordem do `delete_session` do Agno (transcrições, runs e sessão),
    com as compactações junto. No consumo e nos runs registrados, o id vira pseudônimo.
    """
    from app.models.caller_budget import CallerBudget
    from app.models.eval import EvalCase

    counts: dict[str, int] = {}
    engine = get_engine()
    with engine.begin() as conn:
        session_ids = _subject_session_ids(conn, user_id)
        counts["transcripts"] = _delete(
            conn, agno_table(conn, "transcripts"), "session_id", session_ids
        )
        counts["compactions"] = _delete(
            conn, agno_table(conn, "compactions"), "session_id", session_ids
        )
        counts["runs"] = _delete(conn, agno_table(conn, "runs"), "session_id", session_ids)
        traces = agno_table(conn, "traces")
        trace_ids: list[Any] = []
        if traces is not None:
            trace_ids = list(
                conn.scalars(select(traces.c.trace_id).where(traces.c.user_id == user_id))
            )
        counts["spans"] = _delete(conn, agno_table(conn, "spans"), "trace_id", trace_ids)
        for key in AGNO_BY_USER:
            # runs fora de sessão do titular também saem
            removed = _delete(conn, agno_table(conn, key), "user_id", [user_id])
            counts[key] = counts.get(key, 0) + removed
    alias = pseudonym(user_id)
    with Session(engine) as session:
        run_ids = [
            run_id
            for run_id in session.scalars(
                select(AgentRun.run_id).where(AgentRun.user_id == user_id)
            )
            if run_id
        ]
        counts["agent_runs"] = _affected(
            session.execute(
                update(AgentRun)
                .where(AgentRun.user_id == user_id)
                .values(
                    user_id=alias,
                    review_log=None,
                    screened_tools=None,
                    block_detail=None,
                    # conteúdo de conversa que o run guardava (Fase 43)
                    pending_tools=None,
                    pending_steps=None,
                    error=None,
                )
            )
        )
        counts["usage_events"] = _affected(
            session.execute(
                update(UsageEvent).where(UsageEvent.user_id == user_id).values(user_id=alias)
            )
        )
        # caso de teste criado a partir de conversa do titular perde o vínculo com o run
        counts["eval_cases_unlinked"] = (
            _affected(
                session.execute(
                    update(EvalCase)
                    .where(EvalCase.source_run_id.in_(run_ids))
                    .values(source_run_id=None)
                )
            )
            if run_ids
            else 0
        )
        from app.audit import forget_subject

        counts["audit_events"] = forget_subject(session, user_id, alias)
        from app.channels import subject as channel_subject

        counts["channel_conversations"] = channel_subject.erase(session, user_id)
        # o orçamento é configuração do owner: fica, com o pseudônimo no lugar do id. Apagar
        # deixava quem estourou o próprio orçamento pedir a exclusão e voltar a gastar (Fase 43)
        if session.get(CallerBudget, alias) is not None:
            counts["caller_budget"] = _affected(
                session.execute(delete(CallerBudget).where(CallerBudget.subject == user_id))
            )
        else:
            counts["caller_budget"] = _affected(
                session.execute(
                    update(CallerBudget)
                    .where(CallerBudget.subject == user_id)
                    .values(subject=alias)
                )
            )
        session.commit()
    return counts


def new_erase_request(session: Session, user_id: str, actor: str, source: str) -> UUID:
    """Grava o pedido de exclusão sem o id em claro e derruba as exportações do titular.

    Quem chama roda `run_erase(id, user_id)` em seguida, com o id só no argumento.
    """
    erase_request = DataSubjectRequest(
        kind="erase",
        subject=None,
        subject_hash=subject_hash(user_id),
        status="pending",
        requested_by=actor,
        source=source,
        due_at=due_date(),
    )
    session.add(erase_request)
    for export_request in session.scalars(
        select(DataSubjectRequest).where(
            DataSubjectRequest.kind == "export",
            DataSubjectRequest.subject_hash == erase_request.subject_hash,
        )
    ):
        export_request.result = None
        export_request.subject = None
        export_request.expires_at = None
        if export_request.status == "done":
            export_request.status = "expired"
    session.commit()
    return erase_request.id


def run_erase(request_id: UUID, user_id: str) -> None:
    """Background: o id em claro só existe nesta chamada, nunca no pedido gravado."""
    _finish(request_id, status="running")
    try:
        counts = erase(user_id)
        from app import caller_budget

        caller_budget.forget(user_id)
        _finish(request_id, status="done", counts=counts)
        logger.info("titular apagado", extra={"request_id": str(request_id)})
    except Exception as exc:
        logger.warning("exclusão do titular falhou", extra={"request_id": str(request_id)})
        _finish(request_id, status="failed", error=str(exc)[:500])


DATA_SUBJECT_FAILED = "data_subject.failed"
# exportação e exclusão terminam em minutos; parado há mais que isso, o processo caiu
STALE_REQUEST = timedelta(hours=1)
DATA_SUBJECT_DUE = "data_subject.due"
# o aviso de vencimento sai com essa folga antes do prazo
DUE_NOTICE = timedelta(days=2)


def due_date(now: datetime | None = None) -> datetime:
    """Prazo de resposta do pedido, `DATA_SUBJECT_DEADLINE_DAYS` depois de `now`."""
    return (now or datetime.now(UTC)) + timedelta(days=get_settings().data_subject_deadline_days)


def _claim(session: Session, request_id: UUID, column: str, now: datetime) -> bool:
    """Marca o aviso no próprio pedido; False quando ele já saiu (aqui ou em outra réplica)."""
    field = getattr(DataSubjectRequest, column)
    updated = session.execute(
        update(DataSubjectRequest)
        .where(DataSubjectRequest.id == request_id, field.is_(None))
        .values({column: now})
    )
    session.commit()
    return _affected(updated) > 0


def check_requests(session: Session, now: datetime) -> list[tuple[UUID, str]]:
    """Rodada do poller de avisos (ADR-0036): pedido que falhou e pedido perto do prazo."""
    from app.alerts import broadcast, destinations_for

    sent: list[tuple[UUID, str]] = []
    # pedido que roda em background e parou no meio de um deploy (OPS-07): vira falha, e
    # o aviso de falha abaixo pede para refazer
    session.execute(
        update(DataSubjectRequest)
        .where(
            DataSubjectRequest.status.in_(["pending", "running"]),
            DataSubjectRequest.created_at < now - STALE_REQUEST,
        )
        .values(status="failed", error="interrompido antes de terminar", finished_at=now)
    )
    session.commit()
    if destinations_for(session, DATA_SUBJECT_FAILED):
        failed = session.scalars(
            select(DataSubjectRequest).where(
                DataSubjectRequest.status == "failed",
                DataSubjectRequest.failed_alerted_at.is_(None),
            )
        ).all()
        for row in failed:
            if not _claim(session, row.id, "failed_alerted_at", now):
                continue
            # a exclusão não guarda o id: o aviso pede para refazer o pedido
            retry_hint = "Refaça o pedido com o id do titular." if row.kind == "erase" else ""
            broadcast(
                session,
                DATA_SUBJECT_FAILED,
                {"request_id": str(row.id), "kind": row.kind, "source": row.source},
                f"Pedido de {_KIND[row.kind]} do titular {row.subject_hash[:12]} falhou. "
                f"{retry_hint}",
            )
            sent.append((row.id, DATA_SUBJECT_FAILED))
    if destinations_for(session, DATA_SUBJECT_DUE):
        late = session.scalars(
            select(DataSubjectRequest).where(
                DataSubjectRequest.status.in_(["pending", "running"]),
                DataSubjectRequest.due_at.is_not(None),
                DataSubjectRequest.due_at <= now + DUE_NOTICE,
                DataSubjectRequest.due_alerted_at.is_(None),
            )
        ).all()
        for row in late:
            if row.due_at is None or not _claim(session, row.id, "due_alerted_at", now):
                continue
            broadcast(
                session,
                DATA_SUBJECT_DUE,
                {
                    "request_id": str(row.id),
                    "kind": row.kind,
                    "due_at": row.due_at.isoformat(),
                },
                f"Pedido de {_KIND[row.kind]} do titular {row.subject_hash[:12]} segue sem "
                f"resposta; o prazo é {row.due_at:%d/%m/%Y}.",
            )
            sent.append((row.id, DATA_SUBJECT_DUE))
    return sent


# nome do tipo de pedido no texto dos avisos
_KIND = {"export": "exportação", "erase": "exclusão"}
