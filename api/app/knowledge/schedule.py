"""Sincronização agendada de conector e reindexação agendada de URL (ADR-0024).

O poller da API reivindica o que venceu com `FOR UPDATE SKIP LOCKED` e marca o
próximo horário no mesmo commit, antes de trabalhar: duas réplicas não pegam o
mesmo item, e uma origem fora do ar não é tentada a cada minuto.
"""

import hashlib
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.fetch import FetchFailed, fetch_url
from app.knowledge.ingest import CONTENT_TYPES, ingest, remove_chunks
from app.mcp.egress import EgressDenied
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_connector import KnowledgeConnector
from app.models.knowledge_content import KnowledgeContent
from app.settings import get_settings

logger = logging.getLogger(__name__)

# por rodada do poller: o resto fica para o minuto seguinte
BATCH = 10


def next_at(hours: int | None, now: datetime | None = None) -> datetime | None:
    return (now or datetime.now(UTC)) + timedelta(hours=hours) if hours else None


def claim_due(now: datetime | None = None) -> tuple[list[UUID], list[UUID]]:
    """Conectores e conteúdos de URL vencidos, já com o próximo horário marcado."""
    now = now or datetime.now(UTC)
    with Session(get_engine()) as session:
        connectors = session.scalars(
            select(KnowledgeConnector)
            .where(
                KnowledgeConnector.next_sync_at.is_not(None),
                KnowledgeConnector.next_sync_at <= now,
                KnowledgeConnector.last_status != "running",
            )
            .order_by(KnowledgeConnector.next_sync_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        ).all()
        for c in connectors:
            c.next_sync_at = next_at(c.sync_every_hours, now)
            c.last_status = "running"
            c.last_message = None
        contents = session.scalars(
            select(KnowledgeContent)
            .where(
                KnowledgeContent.source_type == "url",
                KnowledgeContent.next_refresh_at.is_not(None),
                KnowledgeContent.next_refresh_at <= now,
                KnowledgeContent.status != "processing",
            )
            .order_by(KnowledgeContent.next_refresh_at)
            .limit(BATCH)
            .with_for_update(skip_locked=True)
        ).all()
        for content in contents:
            content.next_refresh_at = next_at(content.refresh_every_hours, now)
        session.commit()
        return [c.id for c in connectors], [c.id for c in contents]


def _fail(content_id: UUID, message: str) -> None:
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(status="failed", status_message=message[:500])
        )
        session.commit()


def refresh_url(content_id: UUID) -> bool:
    """Baixa a URL de novo e reindexa só se o conteúdo mudou; devolve se reindexou."""
    with Session(get_engine()) as session:
        content = session.get(KnowledgeContent, content_id)
        base = session.get(KnowledgeBase, content.base_id) if content else None
        if content is None or base is None or content.source_type != "url":
            return False
        session.expunge_all()
    max_bytes = get_settings().knowledge_max_upload_mb * 1024 * 1024
    try:
        fetched = fetch_url(content.source, max_bytes)
        extension = CONTENT_TYPES.get(fetched.content_type)
        if extension is None:
            raise FetchFailed(f"tipo de conteúdo não suportado: {fetched.content_type or '?'}")
    except (FetchFailed, EgressDenied, OSError) as exc:
        # página fora do ar não apaga o que já está indexado: só registra o motivo
        logger.warning(
            "reindexação falhou", extra={"content_id": str(content_id), "error": str(exc)}
        )
        if content.status != "completed":
            _fail(content_id, str(exc))
        return False
    digest = hashlib.sha256(fetched.data).hexdigest()
    if content.status == "completed" and digest == content.content_hash:
        return False
    remove_chunks(base, content_id)
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(
                status="processing",
                status_message=None,
                chunk_count=0,
                extension=extension,
                size_bytes=len(fetched.data),
            )
        )
        session.commit()
    ingest(content_id, fetched.data)
    logger.info("URL reindexada", extra={"content_id": str(content_id)})
    return True
