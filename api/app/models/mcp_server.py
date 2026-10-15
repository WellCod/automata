import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class McpServer(Base):
    """Servidor MCP externo consumido pelos agentes (ADR-0010). Não versionado."""

    __tablename__ = "mcp_server"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    # vira tool_name_prefix: evita colisão de nome de tool entre servidores
    slug: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    headers_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    header_names: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    tools_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    tools_discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
