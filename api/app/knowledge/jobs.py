"""Despacho da ingestão (ADR-0039): no processo da API ou na fila do worker separado.

Com `INGEST_WORKER=true` a API só grava o job em `ingest_job`; o
`python -m app.knowledge.worker` executa. Sem a variável, tudo segue em
`BackgroundTasks`, como antes. Os cinco tipos são os caminhos que já existiam.
"""

import logging
from typing import Any, Literal
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.connector_sync import sync
from app.knowledge.fetch import FetchFailed, fetch_url
from app.knowledge.ingest import CONTENT_TYPES, ingest
from app.knowledge.reprocess import original_of, reprocess
from app.knowledge.schedule import refresh_url
from app.mcp.egress import EgressDenied
from app.models.ingest_job import IngestJob
from app.models.knowledge_content import KnowledgeContent
from app.settings import get_settings

logger = logging.getLogger(__name__)

Kind = Literal["ingest", "url", "refresh", "sync", "reprocess"]
# tipos cujo alvo é um conteúdo: o painel mostra "na fila"
CONTENT_KINDS = ("ingest", "url", "refresh")


def worker_enabled() -> bool:
    return get_settings().ingest_worker


def fail_content(content_id: UUID, message: str) -> None:
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(status="failed", status_message=message[:500])
        )
        session.commit()


def ingest_url(content_id: UUID) -> None:
    """Baixa a URL do conteúdo e indexa; a resposta do POST não espera o site."""
    with Session(get_engine()) as session:
        url = session.scalar(
            select(KnowledgeContent.source).where(KnowledgeContent.id == content_id)
        )
    if url is None:
        return
    max_bytes = get_settings().knowledge_max_upload_mb * 1024 * 1024
    try:
        fetched = fetch_url(url, max_bytes)
        extension = CONTENT_TYPES.get(fetched.content_type)
        if extension is None:
            raise FetchFailed(f"tipo de conteúdo não suportado: {fetched.content_type or '?'}")
    except (FetchFailed, EgressDenied, OSError) as exc:
        fail_content(content_id, str(exc))
        logger.warning("download falhou", extra={"content_id": str(content_id), "error": str(exc)})
        return
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(extension=extension, size_bytes=len(fetched.data))
        )
        session.commit()
    ingest(content_id, fetched.data)


def ingest_original(content_id: UUID) -> None:
    """Arquivo e texto pelo original guardado (ADR-0029): o job não carrega os bytes."""
    data = original_of(content_id)
    if data is None:
        fail_content(content_id, "sem o original: envie o arquivo de novo")
        return
    ingest(content_id, data)


def execute(kind: str, target_id: UUID, payload: dict[str, Any] | None = None) -> None:
    if kind == "ingest":
        ingest_original(target_id)
    elif kind == "url":
        ingest_url(target_id)
    elif kind == "refresh":
        refresh_url(target_id)
    elif kind == "sync":
        sync(target_id)
    elif kind == "reprocess":
        ids = (payload or {}).get("content_ids") or []
        reprocess([UUID(str(i)) for i in ids])
    else:
        raise ValueError(f"tipo de job desconhecido: {kind}")


def enqueue(
    session: Session, kind: Kind, target_id: UUID, payload: dict[str, Any] | None = None
) -> None:
    session.add(IngestJob(kind=kind, target_id=target_id, payload=payload, status="queued"))


def submit(
    background: BackgroundTasks | None,
    kind: Kind,
    target_id: UUID,
    payload: dict[str, Any] | None = None,
) -> None:
    """Fila do worker quando ligado; senão `BackgroundTasks` (ou na hora, sem ele)."""
    if worker_enabled():
        with Session(get_engine()) as session:
            enqueue(session, kind, target_id, payload)
            session.commit()
        return
    if background is None:
        execute(kind, target_id, payload)
    else:
        background.add_task(execute, kind, target_id, payload)


def queued_contents(session: Session, content_ids: list[UUID]) -> set[UUID]:
    """Conteúdos com job esperando o worker; vazio com o worker desligado."""
    if not content_ids or not worker_enabled():
        return set()
    return set(
        session.scalars(
            select(IngestJob.target_id).where(
                IngestJob.status == "queued",
                IngestJob.kind.in_(CONTENT_KINDS),
                IngestJob.target_id.in_(content_ids),
            )
        )
    )
