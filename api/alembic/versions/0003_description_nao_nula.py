"""description_nao_nula

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE agent_config SET description = '' WHERE description IS NULL")
    op.alter_column("agent_config", "description", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.alter_column("agent_config", "description", existing_type=sa.Text(), nullable=True)
