"""sessao e tools pendentes de confirmacao no agent_run

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # retomar um run pausado exige o session_id, e o painel precisa das tools pendentes
    op.add_column("agent_run", sa.Column("session_id", sa.String(255), nullable=True))
    op.add_column("agent_run", sa.Column("pending_tools", postgresql.JSONB, nullable=True))
    op.create_index("ix_agent_run_status", "agent_run", ["status"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_status", table_name="agent_run")
    op.drop_column("agent_run", "pending_tools")
    op.drop_column("agent_run", "session_id")
