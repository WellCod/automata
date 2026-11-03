"""agent_run.screened_tools: resultados de tool retirados (ADR-0030)

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # tool, regra, termo e trecho mascarado; o run segue sem o resultado retirado
    op.add_column("agent_run", sa.Column("screened_tools", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "screened_tools")
