"""Reranker da base a partir da estratégia gravada (ADR-0017 e ADR-0033).

As peças são do Agno 3.x; a escolha e os parâmetros vêm do `retrieval` da base.
O cross-encoder é chamado pelo `_rerank`: o `rerank` público do Agno engole o erro
e devolve a lista original, e a busca cobraria por uma ordem que não aconteceu.
"""

import os
from typing import TYPE_CHECKING

from agno.knowledge.document import Document
from agno.knowledge.reranker.base import Reranker
from agno.knowledge.reranker.mmr import MMRReranker
from agno.knowledge.reranker.recency import RecencyReranker
from agno.knowledge.utils import STORE_RECENCY_METADATA_KEY

from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import CrossEncoderSettings, RetrievalSettings

if TYPE_CHECKING:
    from agno.knowledge.reranker.cohere import CohereReranker

# dólares por busca, de até 100 candidatos (tabela pública dos provedores em 2026-11)
CROSS_ENCODER_PRICES: dict[str, float] = {
    "cohere:rerank-v3.5": 0.002,
    "cohere:rerank-multilingual-v3.0": 0.002,
    "bedrock:cohere.rerank-v3-5:0": 0.002,
    "bedrock:amazon.rerank-v1:0": 0.001,
}


def cross_encoder_available(provider: str) -> bool:
    """O provedor de cross-encoder tem o que precisa no ambiente para ser chamado."""
    if provider == "cohere":
        return bool(os.environ.get("COHERE_API_KEY"))
    if provider == "bedrock":
        # o boto3 acha as credenciais pela cadeia padrão; a região precisa ser explícita
        return bool(os.environ.get("AWS_REGION"))
    return False


def cross_encoder_id(settings: CrossEncoderSettings) -> str:
    return f"{settings.provider}:{settings.model}"


# o cliente da Cohere espera 300 s por padrão (OPS-03)
COHERE_TIMEOUT_SECONDS = 30.0


def _timed_cohere(model: str) -> CohereReranker:
    """Reranker da Cohere do Agno com o cliente criado com timeout."""
    from agno.knowledge.reranker.cohere import CohereReranker
    from cohere import Client as CohereClient

    class TimedCohereReranker(CohereReranker):
        # cliente criado só na chamada, como no Agno: sem chave o erro sai na busca
        @property
        def client(self) -> CohereClient:
            if self.cohere_client is None:
                self.cohere_client = CohereClient(
                    api_key=self.api_key, timeout=COHERE_TIMEOUT_SECONDS
                )
            return self.cohere_client

    return TimedCohereReranker(model=model, api_key=os.environ.get("COHERE_API_KEY"))


def cross_encode(
    settings: CrossEncoderSettings, query: str, docs: list[Document]
) -> list[Document]:
    """Ordena por relevância; levanta em falha do provedor."""
    if not docs:
        return docs
    reranker: Reranker
    if settings.provider == "cohere":
        reranker = _timed_cohere(settings.model)
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
    """Reordenação local (MMR ou recência) da base; None quando não há."""
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
