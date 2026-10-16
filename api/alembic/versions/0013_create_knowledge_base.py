"""create_knowledge_base

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_base",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(32), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("embedder", sa.String(32), nullable=False),
        sa.Column("embedder_model", sa.String(128), nullable=False),
        sa.Column("dimensions", sa.Integer, nullable=False),
        sa.Column("chunk_size", sa.Integer, nullable=False, server_default="2000"),
        sa.Column("vector_table", sa.String(63), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("vector_table"),
    )


def downgrade() -> None:
    op.drop_table("knowledge_base")
