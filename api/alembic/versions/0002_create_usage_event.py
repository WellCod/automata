"""create_usage_event

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_event",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(255), nullable=True),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("period", sa.String(6), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost", sa.Numeric(14, 8), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["agent_config_id"], ["agent_config.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_event_agent_config_id", "usage_event", ["agent_config_id"])
    op.create_index("ix_usage_event_period", "usage_event", ["period"])
    op.create_index("ix_usage_event_user_id", "usage_event", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_usage_event_user_id", table_name="usage_event")
    op.drop_index("ix_usage_event_period", table_name="usage_event")
    op.drop_index("ix_usage_event_agent_config_id", table_name="usage_event")
    op.drop_table("usage_event")
