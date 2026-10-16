import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class KnowledgeBase(Base):
    """Base de conhecimento consultada pelos agentes (ADR-0012). Não versionada."""

    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # vira o nome da tool de busca do agente (buscar_<slug>)
    slug: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    # o agente lê a descrição para decidir quando buscar nesta base
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # embedder, modelo e dimensões são fixos: trocar exige reindexar tudo
    embedder: Mapped[str] = mapped_column(String(32), nullable=False)
    embedder_model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    # tabela do PgVector no schema "ai"; criada pelo Agno na primeira ingestão
    vector_table: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
