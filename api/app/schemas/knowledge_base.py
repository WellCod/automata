from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.knowledge.embedders import EmbedderName

_SLUG = r"^[a-z][a-z0-9_]{1,30}$"


class RetrievalSettings(BaseModel):
    """Estratégia de busca da base (ADR-0017): vale para todos os agentes que a usam."""

    # none: busca híbrida de sempre; mmr: trechos relevantes e diferentes entre si;
    # recency: prefere o trecho mais novo sem descartar a relevância
    reranker: Literal["none", "mmr", "recency"] = "none"
    # 1 só relevância, 0 só diversidade
    mmr_lambda: float = Field(default=0.5, ge=0.0, le=1.0)
    # idade em que o peso da recência cai pela metade
    recency_half_life_days: float = Field(default=30.0, gt=0.0, le=3650.0)
    # 0 só relevância, 1 só idade
    recency_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    # busca com uma resposta hipotética no lugar da pergunta: uma chamada de modelo por busca
    hyde: bool = False
    # sempre explícito: sem modelo, o HyDE do Agno cairia num modelo da OpenAI
    hyde_model: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def hyde_com_modelo(self) -> "RetrievalSettings":
        if self.hyde and not self.hyde_model:
            raise ValueError("Escolha o modelo do HyDE")
        return self


class ChunkingSettings(BaseModel):
    """Como o conteúdo da base é cortado em trechos (ADR-0029); vale para novas ingestões."""

    # recursive: o corte de antes; headings: uma seção de markdown por trecho;
    # paragraphs: junta parágrafos até o tamanho; fixed: tamanho fixo
    strategy: Literal["recursive", "headings", "paragraphs", "fixed"] = "recursive"
    # caracteres repetidos entre trechos vizinhos; vazio = 10% do tamanho do trecho
    overlap: int | None = Field(default=None, ge=0)
    # só em headings: até que nível de título abre um trecho (# = 1)
    heading_level: int = Field(default=2, ge=1, le=3)


MAX_OVERLAP_RATIO = 0.3


def overlap_problem(chunk_size: int, chunking: ChunkingSettings | None) -> str | None:
    if chunking is None or chunking.overlap is None:
        return None
    if chunking.overlap > chunk_size * MAX_OVERLAP_RATIO:
        return f"A sobreposição passa de 30% do tamanho do trecho ({chunk_size})"
    return None


class KnowledgeBaseUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(
        default="", max_length=2000, description="Usada pelo agente para decidir quando buscar"
    )
    chunk_size: int = Field(default=2000, ge=200, le=8000, description="Vale para novas ingestões")
    # ausente no PUT mantém a estratégia gravada; na criação vale a busca simples
    retrieval: RetrievalSettings | None = None
    # ausente no PUT mantém o corte gravado; na criação vale a recursiva
    chunking: ChunkingSettings | None = None

    @model_validator(mode="after")
    def sobreposicao_menor(self) -> "KnowledgeBaseUpdate":
        problem = overlap_problem(self.chunk_size, self.chunking)
        if problem:
            raise ValueError(problem)
        return self


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
    retrieval: RetrievalSettings
    chunking: ChunkingSettings
    # ingestão e buscas desde a criação (ADR-0012)
    embedding_tokens: int = 0
    embedding_cost: float | None = None
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
    # baixa de novo nesse intervalo e reindexa se mudou (ADR-0024); vazio = nunca
    refresh_every_hours: int | None = Field(default=None, ge=1, le=168)


class ContentScheduleInput(BaseModel):
    refresh_every_hours: int | None = Field(default=None, ge=1, le=168)


class TextContentInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)


class KnowledgeContentResponse(BaseModel):
    id: UUID
    base_id: UUID
    name: str
    source_type: Literal["file", "url", "text", "connector"]
    source: str
    extension: str
    size_bytes: int
    status: Literal["processing", "completed", "failed"]
    status_message: str | None
    chunk_count: int
    # trechos com instrução embutida para o assistente (ADR-0030); seguem indexados
    suspect_chunks: int = 0
    created_by: str
    created_at: datetime
    updated_at: datetime
    # conteúdo de conector (ADR-0024): o conector e o caminho na origem
    connector_id: UUID | None = None
    external_path: str | None = None
    refresh_every_hours: int | None = None
    next_refresh_at: datetime | None = None


class ChunkPreviewInput(BaseModel):
    """Texto colado ou um conteúdo da base; a estratégia vazia é a gravada na base."""

    text: str | None = Field(default=None, min_length=1, max_length=50_000)
    content_id: UUID | None = None
    chunk_size: int | None = Field(default=None, ge=200, le=8000)
    chunking: ChunkingSettings | None = None

    @model_validator(mode="after")
    def uma_origem(self) -> "ChunkPreviewInput":
        if (self.text is None) == (self.content_id is None):
            raise ValueError("Mande um texto ou um conteúdo da base")
        return self


class ChunkPreview(BaseModel):
    chunks: list[str]
    # trechos que o conteúdo inteiro daria; a lista traz só os primeiros
    total: int
    chunk_size: int
    chunking: ChunkingSettings


class ReprocessResult(BaseModel):
    # reprocessados em background
    queued: int
    # arquivo ou texto enviado antes da Fase 31, sem original guardado
    needs_upload: list["KnowledgeContentResponse"]
    # em processamento agora: ficam como estão
    skipped: int


class SearchInput(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    max_results: int = Field(default=5, ge=1, le=20)


class SearchResult(BaseModel):
    hits: list["SearchHit"]
    # texto que foi de fato buscado: com HyDE, a resposta hipotética
    searched: str
    # tokens do HyDE nesta busca; na busca de teste não são atribuídos a agente nenhum
    hyde_tokens: int


class SearchComparison(BaseModel):
    with_strategy: SearchResult
    without_strategy: SearchResult
    retrieval: RetrievalSettings


class SearchHit(BaseModel):
    content_id: UUID | None
    content_name: str | None
    source: str | None
    text: str
    score: float | None = Field(description="Combina similaridade e full-text, de 0 a 1")


SearchResult.model_rebuild()
