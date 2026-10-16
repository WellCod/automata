"""Embedders disponíveis para bases de conhecimento (ADR-0012)."""

import hashlib
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from agno.knowledge.embedder.base import Embedder

from app.settings import get_settings

EmbedderName = Literal["voyage", "openai"]
# Voyage distingue texto indexado de pergunta e recomenda informar
InputType = Literal["document", "query"]


@dataclass(frozen=True)
class EmbedderSpec:
    name: EmbedderName
    model: str
    dimensions: int
    key_env: str
    # USD por milhão de tokens; a faixa gratuita da Voyage não é descontada
    price_per_mtok: float


EMBEDDERS: dict[EmbedderName, EmbedderSpec] = {
    "voyage": EmbedderSpec("voyage", "voyage-3.5", 1024, "VOYAGE_API_KEY", 0.06),
    "openai": EmbedderSpec("openai", "text-embedding-3-small", 1536, "OPENAI_API_KEY", 0.02),
}


def embedding_cost(model: str, tokens: int) -> float | None:
    for spec in EMBEDDERS.values():
        if spec.model == model:
            return tokens * spec.price_per_mtok / 1_000_000
    return None


def demo_replay() -> bool:
    return os.environ.get("DEMO_REPLAY", "").lower() in ("1", "true")


def is_configured(spec: EmbedderSpec) -> bool:
    """Chave presente, ou demo offline (o replay usa embedder local)."""
    if demo_replay():
        return True
    if spec.name == "voyage":
        return bool(get_settings().voyage_api_key or os.environ.get(spec.key_env))
    return bool(os.environ.get(spec.key_env))


@dataclass
class HashEmbedder(Embedder):
    """Embedder local e determinístico para DEMO_REPLAY e testes: saco de palavras com hash.

    Não entende sinônimos; serve para a demo funcionar sem chave, não para produção.
    """

    dimensions: int | None = 256

    def get_embedding(self, text: str) -> list[float]:
        size = self.dimensions or 256
        vec = [0.0] * size
        for word in re.findall(r"\w+", text.lower()):
            vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % size] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        return self.get_embedding(text), None

    async def async_get_embedding(self, text: str) -> list[float]:
        return self.get_embedding(text)

    async def async_get_embedding_and_usage(
        self, text: str
    ) -> tuple[list[float], dict[str, Any] | None]:
        return self.get_embedding(text), None


def build_embedder(
    embedder: str, model: str, dimensions: int, input_type: InputType = "document"
) -> Embedder:
    """Embedder da base. No replay, o local com as mesmas dimensões da base."""
    if demo_replay():
        return HashEmbedder(dimensions=dimensions)
    if embedder == "voyage":
        from agno.knowledge.embedder.voyageai import VoyageAIEmbedder

        return VoyageAIEmbedder(
            id=model,
            dimensions=dimensions,
            api_key=get_settings().voyage_api_key,
            request_params={"input_type": input_type},
        )
    if embedder == "openai":
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        return OpenAIEmbedder(id=model, dimensions=dimensions)
    raise ValueError(f"embedder desconhecido: {embedder}")


_CACHE_SIZE = 4


class EmbeddingFailed(RuntimeError):
    pass


def _tokens(usage: dict[str, Any] | None) -> int:
    if not usage:
        return 0
    return int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0)


@dataclass
class MeteredEmbedder(Embedder):
    """Conta os tokens e lembra o que já embedou.

    O cache evita pagar duas vezes pelo mesmo texto: a ingestão embeda o primeiro
    trecho antes do insert, e a busca embeda a pergunta antes do search do PgVector,
    que embedaria de novo. Vetor vazio vira erro: o embedder da OpenAI do Agno
    devolve [] em vez de levantar quando a chamada falha.
    """

    inner: Embedder = field(default_factory=HashEmbedder)
    tokens: int = 0
    _cache: dict[str, tuple[list[float], dict[str, Any] | None]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.dimensions = self.inner.dimensions

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        embedding, usage = self.inner.get_embedding_and_usage(text)
        if not embedding:
            raise EmbeddingFailed("o embedder não devolveu vetor: confira a chave e a cota")
        self.tokens += _tokens(usage)
        # poucas entradas bastam (o primeiro trecho, a pergunta); um PDF inteiro não cabe
        if len(self._cache) >= _CACHE_SIZE:
            self._cache.pop(next(iter(self._cache)))
        self._cache[text] = (embedding, usage)
        return embedding, usage

    def get_embedding(self, text: str) -> list[float]:
        return self.get_embedding_and_usage(text)[0]

    async def async_get_embedding(self, text: str) -> list[float]:
        return self.get_embedding(text)

    async def async_get_embedding_and_usage(
        self, text: str
    ) -> tuple[list[float], dict[str, Any] | None]:
        return self.get_embedding_and_usage(text)
