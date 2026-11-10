import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class AuditEvent(Base):
    """Trilha de auditoria (ADR-0041). Sem FK: a trilha sobrevive ao config apagado."""

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_created", "created_at"),
        Index("ix_audit_event_actor_created", "actor", "created_at"),
        Index("ix_audit_event_config_created", "config_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # id do usuário do painel ou integration:<id>; vazio sem autenticação
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # método e rota modelo, como "POST /api/v1/configs/{config_id}/publish"
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
