"""agent_run.review_log: decisões humanas no workflow (ADR-0028)

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # uma entrada por aprovação, recusa ou edição, na ordem em que aconteceram
    op.add_column("agent_run", sa.Column("review_log", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "review_log")
