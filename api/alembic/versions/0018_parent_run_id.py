"""parent_run_id no agent_run: etapa ligada ao run do workflow

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # consumo do workflow é a soma das etapas, que ficam no agente/time que rodou (ADR-0014)
    op.add_column("agent_run", sa.Column("parent_run_id", sa.String(255), nullable=True))
    op.create_index("ix_agent_run_parent_run_id", "agent_run", ["parent_run_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_parent_run_id", table_name="agent_run")
    op.drop_column("agent_run", "parent_run_id")
