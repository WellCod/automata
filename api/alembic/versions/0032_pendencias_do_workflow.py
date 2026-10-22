"""agent_run.pending_steps: etapas do workflow esperando revisão humana (ADR-0023)

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # resumo para a página Aprovações; os requisitos completos ficam no run do Agno
    op.add_column("agent_run", sa.Column("pending_steps", postgresql.JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "pending_steps")
