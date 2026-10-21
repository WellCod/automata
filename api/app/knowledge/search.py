"""Busca numa base, usada pela busca de teste do painel e pela tool do agente (ADR-0012)."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.rerank import reranker_for
from app.knowledge.runtime import metered, vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.repositories.embedding_usage import record_embedding_usage

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    content_id: UUID | None
    content_name: str | None
    source: str | None
    text: str
    score: float | None


def search_base(
    base: KnowledgeBase, query: str, limit: int, *, agent_config_id: UUID | None = None
) -> list[Hit]:
    reranker = reranker_for(base)
    vector_db = vector_db_for(base, "query", with_dates=reranker is not None)
    if not vector_db.table_exists():
        return []
    # o search do PgVector engole falha do embedder e devolve vazio, que o agente
    # leria como "nada sobre isso"; embedar antes faz a falha aparecer (e o
    # MeteredEmbedder devolve o mesmo vetor ao search, sem segunda chamada)
    embedder = metered(vector_db)
    embedder.get_embedding_and_usage(query)
    # o reranker só resgata trecho que foi buscado: pede um lote maior e corta depois
    docs = vector_db.search(query, limit=reranker.search_limit(limit) if reranker else limit)
    if reranker is not None:
        try:
            # ordena contra a pergunta original
            docs = reranker.rerank(query, docs, limit)[:limit]
        except Exception as exc:
            # busca sem reordenar é melhor que busca nenhuma
            logger.warning(
                "reranker falhou; busca sem reordenar",
                extra={"base_id": str(base.id), "error": str(exc)},
            )
            docs = docs[:limit]
    record_embedding_usage(
        base_id=base.id,
        model=base.embedder_model,
        tokens=embedder.tokens,
        kind="search",
        agent_config_id=agent_config_id,
    )
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
