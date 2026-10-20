"""eval_case: casos de teste por agente e time (ADR-0015)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_case",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("checks", postgresql.JSONB, nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_config_id"], ["agent_config.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_config_id", "name", name="uq_eval_case_nome"),
    )


def downgrade() -> None:
    op.drop_table("eval_case")
