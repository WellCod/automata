"""knowledge_connector e a origem remota do conteúdo (ADR-0024)

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_connector",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_base.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        # repositório, bucket, pasta: nada de segredo
        sa.Column("settings", postgresql.JSONB, nullable=False),
        # token, chave ou client secret, cifrados com MCP_SECRETS_KEY
        sa.Column("secret_encrypted", sa.Text, nullable=True),
        # idle | running | ok | failed
        sa.Column("last_status", sa.String(16), nullable=False, server_default="idle"),
        sa.Column("last_message", sa.Text, nullable=True),
        sa.Column("last_summary", postgresql.JSONB, nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # conteúdo que veio de um conector: some junto com ele
    op.add_column(
        "knowledge_content",
        sa.Column(
            "connector_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_connector.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("knowledge_content", sa.Column("external_path", sa.String(1024), nullable=True))
    # sha do Git, ETag do S3, eTag do Graph: igual, a sincronização não baixa de novo
    op.add_column("knowledge_content", sa.Column("external_version", sa.String(255), nullable=True))
    op.add_column("knowledge_content", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index(
        "ix_knowledge_content_connector_path",
        "knowledge_content",
        ["connector_id", "external_path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_content_connector_path", table_name="knowledge_content")
    for column in ("content_hash", "external_version", "external_path", "connector_id"):
        op.drop_column("knowledge_content", column)
    op.drop_table("knowledge_connector")
