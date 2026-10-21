"""eval_schedule: agendamento da suíte por config, com poller próprio (ADR-0016)

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_schedule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_config_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_config.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cron_expr", sa.String(64), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("target", sa.String(16), nullable=False, server_default="current"),
        sa.Column("judge_model", sa.String(64), nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("eval_run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_eval_schedule_due", "eval_schedule", ["enabled", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_eval_schedule_due", table_name="eval_schedule")
    op.drop_table("eval_schedule")
