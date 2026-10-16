"""Busca numa base, usada pela busca de teste do painel e pela tool do agente (ADR-0012)."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.runtime import vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent


@dataclass
class Hit:
    content_id: UUID | None
    content_name: str | None
    source: str | None
    text: str
    score: float | None


def search_base(base: KnowledgeBase, query: str, limit: int) -> list[Hit]:
    vector_db = vector_db_for(base)
    if not vector_db.table_exists():
        return []
    # o search do PgVector engole falha do embedder e devolve vazio, que o agente
    # leria como "nada sobre isso"; embedar antes faz a falha aparecer
    vector_db.embedder.get_embedding_and_usage(query)
    docs = vector_db.search(query, limit=limit)
    ids: set[UUID] = set()
    for doc in docs:
        raw = (doc.meta_data or {}).get("content_id")
        if raw:
            ids.add(UUID(str(raw)))
    names: dict[UUID, str] = {}
    if ids:
        with Session(get_engine()) as session:
            rows = session.execute(
                select(KnowledgeContent.id, KnowledgeContent.name).where(
                    KnowledgeContent.id.in_(ids)
                )
            )
            names = {row.id: row.name for row in rows}
    hits = []
    for doc in docs:
        meta = doc.meta_data or {}
        content_id = UUID(str(meta["content_id"])) if meta.get("content_id") else None
        score = meta.get("similarity_score")
        hits.append(
            Hit(
                content_id=content_id,
                content_name=names.get(content_id) if content_id else None,
                source=meta.get("source"),
                text=doc.content,
                score=float(score) if score is not None else None,
            )
        )
    return hits
