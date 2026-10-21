"""Reranker da base a partir da estratégia gravada (ADR-0017).

As peças são do Agno 3.x; a escolha e os parâmetros vêm do `retrieval` da base.
"""

from agno.knowledge.reranker.base import Reranker
from agno.knowledge.reranker.mmr import MMRReranker
from agno.knowledge.reranker.recency import RecencyReranker
from agno.knowledge.utils import STORE_RECENCY_METADATA_KEY

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import RetrievalSettings


def reranker_for(base: KnowledgeBase) -> Reranker | None:
    settings = RetrievalSettings.model_validate(base.retrieval or {})
    if settings.reranker == "mmr":
        return MMRReranker(lambda_mult=settings.mmr_lambda)
    if settings.reranker == "recency":
        return RecencyReranker(
            # a data da linha do PgVector, não um campo nosso no meta_data
            timestamp_key=STORE_RECENCY_METADATA_KEY,
            half_life_days=settings.recency_half_life_days,
            weight=settings.recency_weight,
        )
    return None
