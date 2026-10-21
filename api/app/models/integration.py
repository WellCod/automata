import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class IntegrationToken(Base):
    """Token de sistema consumidor (ADR-0009): scopes por agente/time, revogável por jti."""

    __tablename__ = "integration_token"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    team_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # suíte de testes que o token pode rodar e consultar, para o CI do consumidor (ADR-0016)
    eval_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
