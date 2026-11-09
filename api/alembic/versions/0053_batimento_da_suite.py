"""eval_run.heartbeat_at: suíte interrompida só sem batimento (Fase 44)

Revision ID: 0053
Revises: 0052
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eval_run", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_run", "heartbeat_at")
