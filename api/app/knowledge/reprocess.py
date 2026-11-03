"""Reprocessamento da base com o corte atual (ADR-0029).

URL é baixada de novo, arquivo de conector vem da origem pela listagem (o `ref` do
SharePoint é uma URL de download que expira) e arquivo e texto enviados vêm do original
guardado. O que foi enviado antes da Fase 31 não tem original: precisa ser reenviado.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.connector_sync import source_of
from app.knowledge.fetch import FetchFailed, fetch_url
from app.knowledge.ingest import CONTENT_TYPES, ingest, keep_previous, remove_chunks
from app.knowledge.sources import SourceError
from app.mcp.egress import EgressDenied
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_connector import KnowledgeConnector
from app.models.knowledge_content import KnowledgeContent, KnowledgeContentOriginal
from app.settings import get_settings

logger = logging.getLogger(__name__)


def save_original(session: Session, content_id: UUID, data: bytes) -> None:
    session.merge(KnowledgeContentOriginal(content_id=content_id, data=data))


@dataclass
class ReprocessPlan:
    queued: list[UUID] = field(default_factory=list)
    needs_upload: list[KnowledgeContent] = field(default_factory=list)
    skipped: int = 0


def plan_reprocess(session: Session, base_id: UUID) -> ReprocessPlan:
    """Marca como processing o que a base consegue reler; o resto volta na resposta.

    A marcação é condicional (`status <> 'processing'`): duas chamadas ao mesmo tempo
    enfileiram cada conteúdo uma vez só.
    """
    contents = session.scalars(
        select(KnowledgeContent)
        .where(KnowledgeContent.base_id == base_id)
        .order_by(KnowledgeContent.created_at)
    ).all()
    with_original = set(
        session.scalars(
            select(KnowledgeContentOriginal.content_id).where(
                KnowledgeContentOriginal.content_id.in_([c.id for c in contents])
            )
        )
    )
    result = ReprocessPlan()
    candidates: list[UUID] = []
    for content in contents:
        if content.status == "processing":
            result.skipped += 1
        elif content.source_type in ("file", "text") and content.id not in with_original:
            result.needs_upload.append(content)
        else:
            candidates.append(content.id)
    if candidates:
        claimed = set(
            session.scalars(
                update(KnowledgeContent)
                .where(
                    KnowledgeContent.id.in_(candidates),
                    KnowledgeContent.status != "processing",
                )
                .values(status="processing", status_message=None)
                .returning(KnowledgeContent.id)
            )
        )
        result.queued = [c for c in candidates if c in claimed]
        result.skipped += len(candidates) - len(result.queued)
    return result


def _fail(content_id: UUID, message: str) -> None:
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(status="failed", status_message=message[:500], chunk_count=0)
        )
        session.commit()


def _replace(base: KnowledgeBase, content_id: UUID, data: bytes, extension: str | None) -> None:
    if extension is not None:
        with Session(get_engine()) as session:
            session.execute(
                update(KnowledgeContent)
                .where(KnowledgeContent.id == content_id)
                .values(extension=extension, size_bytes=len(data))
            )
            session.commit()
    # os trechos antigos só saem depois de o embedder responder
    ingest(content_id, data, replace=True)


def _original(content_id: UUID) -> bytes | None:
    # um por vez: a base inteira de originais não cabe na memória da API
    with Session(get_engine()) as session:
        return session.scalar(
            select(KnowledgeContentOriginal.data).where(
                KnowledgeContentOriginal.content_id == content_id
            )
        )


def reprocess(content_ids: list[UUID]) -> None:
    """Reprocessa em sequência; uma falha marca só o conteúdo dela."""
    with Session(get_engine()) as session:
        contents = [c for c in (session.get(KnowledgeContent, i) for i in content_ids) if c]
        bases = {c.base_id: session.get(KnowledgeBase, c.base_id) for c in contents}
        session.expunge_all()
    max_bytes = get_settings().knowledge_max_upload_mb * 1024 * 1024
    by_connector: dict[UUID, list[KnowledgeContent]] = defaultdict(list)
    for content in contents:
        base = bases[content.base_id]
        if base is None:
            continue
        try:
            if content.source_type == "url":
                fetched = fetch_url(content.source, max_bytes)
                extension = CONTENT_TYPES.get(fetched.content_type)
                if extension is None:
                    raise FetchFailed(
                        f"tipo de conteúdo não suportado: {fetched.content_type or '?'}"
                    )
                _replace(base, content.id, fetched.data, extension)
            elif content.source_type == "connector" and content.connector_id is not None:
                by_connector[content.connector_id].append(content)
            elif (original := _original(content.id)) is not None:
                _replace(base, content.id, original, None)
            else:
                _fail(content.id, "sem o original: envie o arquivo de novo")
        except (FetchFailed, EgressDenied, OSError) as exc:
            # a origem falhou antes da troca: os trechos anteriores continuam valendo
            keep_previous(content.id, str(exc))
    for connector_id, items in by_connector.items():
        _reprocess_connector(connector_id, items, bases)


def _reprocess_connector(
    connector_id: UUID,
    items: list[KnowledgeContent],
    bases: dict[UUID, KnowledgeBase | None],
) -> None:
    with Session(get_engine()) as session:
        connector = session.get(KnowledgeConnector, connector_id)
        if connector is not None:
            session.expunge(connector)
    if connector is None:
        for content in items:
            _fail(content.id, "conector removido")
        return
    try:
        source = source_of(connector)
        listed = {f.path: f for f in source.list_files()}
    except (SourceError, EgressDenied, OSError) as exc:
        for content in items:
            keep_previous(content.id, f"conector: {exc}")
        return
    for content in items:
        base = bases[content.base_id]
        remote = listed.get(content.external_path or "")
        if base is None or remote is None:
            # sumiu da origem: os trechos saem, como na sincronização do conector
            if base is not None:
                remove_chunks(base, content.id)
            _fail(content.id, "arquivo não está mais na origem")
            continue
        try:
            _replace(base, content.id, source.download(remote), None)
        except (SourceError, EgressDenied, OSError) as exc:
            keep_previous(content.id, str(exc))
    logger.info("conector reprocessado", extra={"connector_id": str(connector_id)})
