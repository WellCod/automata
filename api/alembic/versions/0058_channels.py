"""canais de conversa, conversas e mensagens (ADR-0044)

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_config.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("credentials_encrypted", sa.Text, nullable=False),
        sa.Column("handoff_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "handoff_keywords",
            JSONB,
            nullable=False,
            server_default=sa.text('\'["atendente", "humano"]\'::jsonb'),
        ),
        sa.Column(
            "handoff_message",
            sa.String(500),
            nullable=False,
            server_default="Vou te passar para uma pessoa da equipe. Um momento.",
        ),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "channel_conversation",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_id",
            UUID(as_uuid=True),
            sa.ForeignKey("channel.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="bot"),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("handoff_reason", sa.String(255), nullable=True),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_channel_conversation_external",
        "channel_conversation",
        ["channel_id", "external_id"],
        unique=True,
    )
    op.create_index(
        "ix_channel_conversation_status", "channel_conversation", ["status", "last_message_at"]
    )
    op.create_index("ix_channel_conversation_user", "channel_conversation", ["user_id"])
    op.create_table(
        "channel_message",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_id",
            UUID(as_uuid=True),
            sa.ForeignKey("channel.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("channel_conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_channel_message_external",
        "channel_message",
        ["channel_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_index(
        "ix_channel_message_conversation", "channel_message", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("channel_message")
    op.drop_table("channel_conversation")
    op.drop_table("channel")
