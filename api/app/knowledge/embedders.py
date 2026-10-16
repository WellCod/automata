"""Embedders disponíveis para bases de conhecimento (ADR-0012)."""

import os
from dataclasses import dataclass
from typing import Literal

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
