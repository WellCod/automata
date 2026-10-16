"""runs_bloqueados

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_run", sa.Column("blocked_by", sa.String(32), nullable=True))
    op.add_column("agent_run", sa.Column("block_detail", postgresql.JSONB, nullable=True))
    op.create_index("ix_agent_run_blocked_by", "agent_run", ["blocked_by"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_blocked_by", table_name="agent_run")
    op.drop_column("agent_run", "block_detail")
    op.drop_column("agent_run", "blocked_by")
