"""agent_run.stop_reason: run encerrado antes do fim sem ser erro (ADR-0031)

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ex.: run_cost_limit; o run conta como sucesso, com a parada à vista
    op.add_column("agent_run", sa.Column("stop_reason", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "stop_reason")
