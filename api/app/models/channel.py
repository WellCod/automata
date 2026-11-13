import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base

DEFAULT_HANDOFF_KEYWORDS = ["atendente", "humano"]
DEFAULT_HANDOFF_MESSAGE = "Vou te passar para uma pessoa da equipe. Um momento."


class Channel(Base):
    """Canal de conversa (ADR-0044): um número de WhatsApp ou um app de Slack ligado a
    um agente ou time."""

    __tablename__ = "channel"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # whatsapp | slack
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_config.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # credencial do provedor em JSON cifrado com Fernet (ADR-0026)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    handoff_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    handoff_keywords: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=lambda: list(DEFAULT_HANDOFF_KEYWORDS)
    )
    handoff_message: Mapped[str] = mapped_column(
        String(500), nullable=False, default=DEFAULT_HANDOFF_MESSAGE
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChannelConversation(Base):
    """Uma pessoa num canal; o id é o `session_id` do agente."""

    __tablename__ = "channel_conversation"
    __table_args__ = (
        Index("uq_channel_conversation_external", "channel_id", "external_id", unique=True),
        Index("ix_channel_conversation_status", "status", "last_message_at"),
        Index("ix_channel_conversation_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel.id", ondelete="CASCADE"), nullable=False
    )
    # número no WhatsApp; no Slack, canal e thread
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # whatsapp:<número> ou slack:<usuário>: o user_id do run, da memória e do titular
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # bot | human | closed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="bot")
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    handoff_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ChannelMessage(Base):
    __tablename__ = "channel_message"
    __table_args__ = (
        # o provedor reenvia o que não recebeu 200 a tempo: a mesma mensagem não roda duas vezes
        Index(
            "uq_channel_message_external",
            "channel_id",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_channel_message_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # in | out
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    # customer | agent | system | attendant:<user_id>
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # received | sent | failed | ignored
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
