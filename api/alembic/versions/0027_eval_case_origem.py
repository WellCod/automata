"""eval_case.source_run_id: run de conversa de onde o caso veio (ADR-0016)

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eval_case", sa.Column("source_run_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_case", "source_run_id")
