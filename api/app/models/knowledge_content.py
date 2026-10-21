import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class KnowledgeContent(Base):
    """Documento de uma base (ADR-0012). Os trechos ficam na tabela de vetores da base."""

    __tablename__ = "knowledge_content"
    __table_args__ = (
        Index("ix_knowledge_content_base_created", "base_id", "created_at"),
        Index("ix_knowledge_content_status", "status"),
        # um arquivo da origem é um conteúdo só por conector (ADR-0024)
        Index("ix_knowledge_content_connector_path", "connector_id", "external_path", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_base.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # file | url | text | connector
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # nome do arquivo ou URL de origem
    source: Mapped[str] = mapped_column(String(2048), nullable=False)
    extension: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # processing | completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    # origem remota (ADR-0024): o conector, o caminho lá e a versão lá
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_connector.id", ondelete="CASCADE"),
        nullable=True,
    )
    external_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # sha256 dos bytes ingeridos: a reindexação de URL só indexa de novo se mudar
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # só URL: baixa de novo nesse intervalo e reindexa se o hash mudou
    refresh_every_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_refresh_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
