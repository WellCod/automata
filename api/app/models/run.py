import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        Index("ix_agent_run_config_created", "agent_config_id", "created_at"),
        Index("ix_agent_run_created_at", "created_at"),
        Index("ix_agent_run_run_id", "run_id"),
        Index("ix_agent_run_status", "status"),
        Index("ix_agent_run_blocked_by", "blocked_by"),
        Index("ix_agent_run_parent_run_id", "parent_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_config.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ToolExecution.to_dict() das tools aguardando confirmação; só em run pausado
    pending_tools: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    # status=blocked: regra de guardrail que barrou (ADR-0013) e o detalhe dela
    # (tipos de dado, termo configurado); nunca o valor que o usuário mandou
    blocked_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # run do workflow em que esta etapa rodou
    parent_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    block_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
