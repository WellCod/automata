"""create_embedding_usage

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "embedding_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_config_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("period", sa.String(6), nullable=False),
        sa.Column("tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(14, 8), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["base_id"], ["knowledge_base.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_config_id"], ["agent_config.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_embedding_usage_created_at", "embedding_usage", ["created_at"])
    op.create_index(
        "ix_embedding_usage_period_agent", "embedding_usage", ["period", "agent_config_id"]
    )
    op.create_index("ix_embedding_usage_base", "embedding_usage", ["base_id"])


def downgrade() -> None:
    op.drop_index("ix_embedding_usage_base", table_name="embedding_usage")
    op.drop_index("ix_embedding_usage_period_agent", table_name="embedding_usage")
    op.drop_index("ix_embedding_usage_created_at", table_name="embedding_usage")
    op.drop_table("embedding_usage")
