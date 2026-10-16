"""create_knowledge_content

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_content",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("source", sa.String(2048), nullable=False),
        sa.Column("extension", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
        sa.Column("status_message", sa.Text, nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["base_id"], ["knowledge_base.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_knowledge_content_base_created", "knowledge_content", ["base_id", "created_at"]
    )
    op.create_index("ix_knowledge_content_status", "knowledge_content", ["status"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_content_status", table_name="knowledge_content")
    op.drop_index("ix_knowledge_content_base_created", table_name="knowledge_content")
    op.drop_table("knowledge_content")
