import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class DataSubjectRequest(Base):
    """Pedido de exportação ou exclusão dos dados de um titular (ADR-0032)."""

    __tablename__ = "data_subject_request"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # export, erase
    # sha256 do user_id: o histórico não guarda o id em claro
    subject_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # id em claro só enquanto o arquivo da exportação vale; a exclusão nunca guarda
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # JSON compactado com gzip, só na exportação
    result: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
