"""Ligação de uma base com o Agno: PgVector por base, sem contents_db (ADR-0012)."""

from typing import cast

from agno.vectordb.pgvector import PgVector
from agno.vectordb.search import SearchType

from app.knowledge.embedders import InputType, MeteredEmbedder, build_embedder
from app.models.knowledge_base import KnowledgeBase
from app.settings import get_settings

VECTOR_SCHEMA = "ai"


def vector_db_for(
    base: KnowledgeBase, input_type: InputType = "document", *, with_dates: bool = False
) -> PgVector:
    # híbrida: vetor + full-text em português, que acha termos exatos (siglas, códigos)
    # que o embedding sozinho às vezes perde
    return PgVector(
        table_name=base.vector_table,
        schema=VECTOR_SCHEMA,
        db_url=get_settings().database_url,
        embedder=MeteredEmbedder(
            inner=build_embedder(base.embedder, base.embedder_model, base.dimensions, input_type)
        ),
        search_type=SearchType.hybrid,
        content_language="portuguese",
        # a data da linha vai no meta_data do trecho: só quando o reranker de recência pede
        return_updated_at=with_dates,
    )


def metered(vector_db: PgVector) -> MeteredEmbedder:
    return cast(MeteredEmbedder, vector_db.embedder)
