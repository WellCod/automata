from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

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


class UrlContentInput(BaseModel):
    url: HttpUrl
    name: str | None = Field(default=None, max_length=255)


class TextContentInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)


class KnowledgeContentResponse(BaseModel):
    id: UUID
    base_id: UUID
    name: str
    source_type: Literal["file", "url", "text"]
    source: str
    extension: str
    size_bytes: int
    status: Literal["processing", "completed", "failed"]
    status_message: str | None
    chunk_count: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=20)


class SearchHit(BaseModel):
    content_id: UUID | None
    content_name: str | None
    source: str | None
    text: str
    score: float | None = Field(description="Combina similaridade e full-text, de 0 a 1")
