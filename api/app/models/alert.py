import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class AlertDestination(Base):
    """Destino de aviso da instância (ADR-0021): assina eventos de todos os configs."""

    __tablename__ = "alert_destination"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    webhook_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_host: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    last_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AlertSent(Base):
    __tablename__ = "alert_sent"

    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id", ondelete="CASCADE"), primary_key=True
    )
    event: Mapped[str] = mapped_column(String(32), primary_key=True)
    window: Mapped[str] = mapped_column(String(16), primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
