"""Reranker da base a partir da estratégia gravada (ADR-0017 e ADR-0033).

As peças são do Agno 3.x; a escolha e os parâmetros vêm do `retrieval` da base.
O cross-encoder é chamado pelo `_rerank`: o `rerank` público do Agno engole o erro
e devolve a lista original, e a busca cobraria por uma ordem que não aconteceu.
"""

import os

from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker
from agno.knowledge.reranker.mmr import MMRReranker
from agno.knowledge.reranker.recency import RecencyReranker
from agno.knowledge.utils import STORE_RECENCY_METADATA_KEY

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import CrossEncoderSettings, RetrievalSettings

# dólares por busca, de até 100 candidatos (tabela pública dos provedores em 2026-11)
CROSS_ENCODER_PRICES: dict[str, float] = {
    "cohere:rerank-v3.5": 0.002,
    "cohere:rerank-multilingual-v3.0": 0.002,
    "bedrock:cohere.rerank-v3-5:0": 0.002,
    "bedrock:amazon.rerank-v1:0": 0.001,
}


def cross_encoder_available(provider: str) -> bool:
    if provider == "cohere":
        return bool(os.environ.get("COHERE_API_KEY"))
    if provider == "bedrock":
        # o boto3 acha as credenciais pela cadeia padrão; a região precisa ser explícita
        return bool(os.environ.get("AWS_REGION"))
    return False


def cross_encoder_id(settings: CrossEncoderSettings) -> str:
    return f"{settings.provider}:{settings.model}"


def cross_encode(
    settings: CrossEncoderSettings, query: str, docs: list[Document]
) -> list[Document]:
    """Ordena por relevância; levanta em falha do provedor."""
    if not docs:
        return docs
    reranker: Reranker
    if settings.provider == "cohere":
        from agno.knowledge.reranker.cohere import CohereReranker

        reranker = CohereReranker(model=settings.model, api_key=os.environ.get("COHERE_API_KEY"))
    else:
        from agno.knowledge.reranker.aws_bedrock import AwsBedrockReranker

        reranker = AwsBedrockReranker(model=settings.model, aws_region=os.environ.get("AWS_REGION"))
    ranked: list[Document] = reranker._rerank(query=query, documents=docs)
    return ranked


def candidate_limit(base: KnowledgeBase, limit: int) -> int:
    """Lote pedido ao banco: com qualquer reordenação, maior que o K."""
    settings = RetrievalSettings.model_validate(base.retrieval or {})
    strategy = reranker_for(base)
    if strategy is not None:
        return strategy.search_limit(limit)
    if settings.cross_encoder is not None:
        # mesmo lote do Reranker do Agno: 3 vezes o K, até 100
        return max(min(limit * 3, 100), limit)
    return limit


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
