"""knowledge_content.fields: campos próprios do documento para os filtros (ADR-0033)

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_content", sa.Column("fields", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_content", "fields")
