"""Embedders disponíveis para bases de conhecimento (ADR-0012)."""

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

from agno.knowledge.embedder.base import Embedder

from app.settings import get_settings

EmbedderName = Literal["voyage", "openai"]


@dataclass(frozen=True)
class EmbedderSpec:
    name: EmbedderName
    model: str
    dimensions: int
    key_env: str


EMBEDDERS: dict[EmbedderName, EmbedderSpec] = {
    "voyage": EmbedderSpec("voyage", "voyage-3.5", 1024, "VOYAGE_API_KEY"),
    "openai": EmbedderSpec("openai", "text-embedding-3-small", 1536, "OPENAI_API_KEY"),
}


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


def build_embedder(embedder: str, model: str, dimensions: int) -> Embedder:
    """Embedder da base. No replay, o local com as mesmas dimensões da base."""
    if demo_replay():
        return HashEmbedder(dimensions=dimensions)
    if embedder == "voyage":
        from agno.knowledge.embedder.voyageai import VoyageAIEmbedder

        return VoyageAIEmbedder(
            id=model, dimensions=dimensions, api_key=get_settings().voyage_api_key
        )
    if embedder == "openai":
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        return OpenAIEmbedder(id=model, dimensions=dimensions)
    raise ValueError(f"embedder desconhecido: {embedder}")
