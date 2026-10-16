"""Ingestão em background: lê, quebra em trechos, gera embeddings e grava (ADR-0012).

Roda numa thread do processo da API (BackgroundTasks). O estado fica em
knowledge_content; restart no meio deixa a linha em processing, e o boot
marca como falha o que estiver parado há mais de STALE_AFTER.
"""

import hashlib
import io
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.document.base import Document
from agno.knowledge.reader.base import Reader
from agno.knowledge.reader.reader_factory import ReaderFactory
from agno.vectordb.pgvector import PgVector
from bs4 import BeautifulSoup
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.runtime import metered, vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.repositories.embedding_usage import record_embedding_usage

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(minutes=30)
_MAX_MESSAGE = 500

# content-type da resposta HTTP para a extensão do leitor
CONTENT_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/markdown": "md",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/json": "json",
    "text/html": "html",
}


class IngestError(ValueError):
    pass


def _reader(extension: str, chunk_size: int) -> Reader:
    reader = ReaderFactory.get_reader_for_extension(f".{extension}")
    reader.chunk = True
    reader.chunking_strategy = RecursiveChunking(chunk_size=chunk_size, overlap=chunk_size // 10)
    return reader


def _html_to_text(data: bytes) -> str:
    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def read_documents(name: str, extension: str, data: bytes, chunk_size: int) -> list[Document]:
    if extension == "html":
        extension, data = "txt", _html_to_text(data).encode()
    stream = io.BytesIO(data)
    stream.name = f"{name}.{extension}"
    docs = _reader(extension, chunk_size).read(stream, name=name)
    docs = [d for d in docs if d.content and d.content.strip()]
    if not docs:
        raise IngestError("nenhum texto extraído do conteúdo")
    return docs


def _finish(content_id: UUID, *, status: str, message: str | None, chunks: int = 0) -> None:
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(status=status, status_message=message, chunk_count=chunks)
        )
        session.commit()


def count_chunks(base: KnowledgeBase, content_id: UUID) -> int:
    vector_db = vector_db_for(base)
    if not vector_db.table_exists():
        return 0
    with Session(get_engine()) as session:
        stmt = (
            select(func.count())
            .select_from(vector_db.table)
            .where(vector_db.table.c.content_id == str(content_id))
        )
        return int(session.execute(stmt).scalar_one())


def remove_chunks(base: KnowledgeBase, content_id: UUID) -> None:
    vector_db = vector_db_for(base)
    if vector_db.table_exists():
        vector_db.delete_by_content_id(str(content_id))


def ingest(content_id: UUID, data: bytes) -> None:
    """Processa o conteúdo já registrado como processing. Nunca levanta: grava a falha."""
    base: KnowledgeBase | None = None
    vector_db: PgVector | None = None
    try:
        with Session(get_engine()) as session:
            content = session.get(KnowledgeContent, content_id)
            base = session.get(KnowledgeBase, content.base_id) if content else None
            if content is None or base is None:
                return
            session.expunge_all()
        docs = read_documents(content.name, content.extension, data, base.chunk_size)
        vector_db = vector_db_for(base)
        vector_db.create()
        # o insert do PgVector loga e pula trecho cujo embedding falha; embedar o
        # primeiro aqui faz o erro real (chave inválida, cota) virar a mensagem.
        # O MeteredEmbedder guarda esse vetor: o insert não paga de novo
        docs[0].embed(vector_db.embedder)
        for doc in docs:
            doc.content_id = str(content_id)
            doc.meta_data = {
                **(doc.meta_data or {}),
                "content_id": str(content_id),
                "source": content.source,
            }
        vector_db.insert(content_hash=hashlib.sha256(data).hexdigest(), documents=docs)
        stored = count_chunks(base, content_id)
        if stored < len(docs):
            vector_db.delete_by_content_id(str(content_id))
            raise IngestError(f"{len(docs) - stored} de {len(docs)} trechos não foram indexados")
        _finish(content_id, status="completed", message=None, chunks=stored)
        logger.info(
            "conteúdo indexado",
            extra={"content_id": str(content_id), "base_id": str(base.id), "chunks": stored},
        )
    except Exception as exc:
        logger.warning("ingestão falhou", extra={"content_id": str(content_id), "error": str(exc)})
        _finish(content_id, status="failed", message=str(exc)[:_MAX_MESSAGE])
    finally:
        # cobra também o que foi gasto antes de uma falha no meio
        if base is not None and vector_db is not None:
            try:
                record_embedding_usage(
                    base_id=base.id,
                    model=base.embedder_model,
                    tokens=metered(vector_db).tokens,
                    kind="ingest",
                )
            except Exception as exc:
                logger.warning("falha ao registrar consumo", extra={"error": str(exc)})


def fail_stale(now: datetime | None = None) -> int:
    """Conteúdo preso em processing (restart no meio da ingestão) vira falha."""
    limit = (now or datetime.now(UTC)) - STALE_AFTER
    with Session(get_engine()) as session:
        result = session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.status == "processing", KnowledgeContent.updated_at < limit)
            .values(status="failed", status_message="interrompido por reinício da API; reenvie")
        )
        session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
