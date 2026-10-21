import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class KnowledgeConnector(Base):
    """Origem remota de uma base (ADR-0024): cada arquivo vira um knowledge_content."""

    __tablename__ = "knowledge_connector"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_base.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # github | s3 | sharepoint
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    # idle | running | ok | failed
    last_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="idle", default="idle"
    )
    last_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # vazio = só manual (ADR-0024)
    sync_every_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
