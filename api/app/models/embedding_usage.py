import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class EmbeddingUsage(Base):
    """Tokens de embedding gastos em ingestão e busca (ADR-0012).

    Separado de usage_event, que é por run de agente: ingestão não tem agente, e
    busca de teste no painel também não.
    """

    __tablename__ = "embedding_usage"
    __table_args__ = (
        Index("ix_embedding_usage_created_at", "created_at"),
        Index("ix_embedding_usage_period_agent", "period", "agent_config_id"),
        Index("ix_embedding_usage_base", "base_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # SET NULL: remover base ou agente não apaga o histórico de custo
    base_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_base.id", ondelete="SET NULL"), nullable=True
    )
    agent_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id", ondelete="SET NULL"), nullable=True
    )
    # ingest | search
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    period: Mapped[str] = mapped_column(String(6), nullable=False)  # YYYYMM
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[float | None] = mapped_column(Numeric(14, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
