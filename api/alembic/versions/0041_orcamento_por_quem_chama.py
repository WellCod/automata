"""caller_budget: orçamento mensal por usuário e por token de integração (ADR-0031)

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "caller_budget",
        sa.Column("subject", sa.String(255), primary_key=True),
        sa.Column("monthly_usd", sa.Numeric(12, 4), nullable=False),
        sa.Column("warn_percent", sa.Integer, nullable=False, server_default="80"),
        sa.Column("hard_stop", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("warned_period", sa.String(6), nullable=True),
        sa.Column("exceeded_period", sa.String(6), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # o gasto do mês por quem chama soma o usage_event por user_id e período
    op.create_index("ix_usage_event_user_period", "usage_event", ["user_id", "period"])


def downgrade() -> None:
    op.drop_index("ix_usage_event_user_period", table_name="usage_event")
    op.drop_table("caller_budget")
