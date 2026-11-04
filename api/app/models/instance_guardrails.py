from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class InstanceGuardrails(Base):
    """Piso de guardrails que todo agente e líder de time herda (ADR-0034). Uma linha só."""

    __tablename__ = "instance_guardrails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # GuardrailSettings; o agente só endurece o que está aqui
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
