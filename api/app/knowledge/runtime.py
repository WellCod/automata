"""Ligação de uma base com o Agno: PgVector por base, sem contents_db (ADR-0012)."""

from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType

from app.knowledge.embedders import build_embedder
from app.models.knowledge_base import KnowledgeBase
from app.settings import get_settings

VECTOR_SCHEMA = "ai"


def vector_db_for(base: KnowledgeBase) -> PgVector:
    # híbrida: vetor + full-text em português, que acha termos exatos (siglas, códigos)
    # que o embedding sozinho às vezes perde
    return PgVector(
        table_name=base.vector_table,
        schema=VECTOR_SCHEMA,
        db_url=get_settings().database_url,
        embedder=build_embedder(base.embedder, base.embedder_model, base.dimensions),
        search_type=SearchType.hybrid,
        content_language="portuguese",
    )
