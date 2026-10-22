"""agent_config: orçamento mensal, aviso e bloqueio ao estourar (ADR-0021)

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_config", sa.Column("budget_monthly_usd", sa.Numeric(12, 2), nullable=True))
    op.add_column(
        "agent_config",
        sa.Column("budget_alert_percent", sa.Integer, nullable=False, server_default="80"),
    )
    op.add_column(
        "agent_config",
        sa.Column("budget_hard_stop", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("agent_config", "budget_hard_stop")
    op.drop_column("agent_config", "budget_alert_percent")
    op.drop_column("agent_config", "budget_monthly_usd")
