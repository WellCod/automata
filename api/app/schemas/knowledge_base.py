from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.knowledge.embedders import EmbedderName

_SLUG = r"^[a-z][a-z0-9_]{1,30}$"


class KnowledgeBaseUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(
        default="", max_length=2000, description="Usada pelo agente para decidir quando buscar"
    )
    chunk_size: int = Field(default=2000, ge=200, le=8000, description="Vale para novas ingestões")


class KnowledgeBaseCreate(KnowledgeBaseUpdate):
    slug: str = Field(pattern=_SLUG, description="Nome da tool de busca; não muda depois")
    embedder: EmbedderName | None = Field(
        default=None, description="Vazio usa KNOWLEDGE_DEFAULT_EMBEDDER; não muda depois"
    )


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str
    embedder: str
    embedder_model: str
    dimensions: int
    chunk_size: int
    updated_by: str
    created_at: datetime
    updated_at: datetime


class EmbedderInfo(BaseModel):
    name: EmbedderName
    model: str
    dimensions: int
    configured: bool
    default: bool
