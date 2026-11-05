"""knowledge_connector.webhook_secret_encrypted: webhook da origem (ADR-0039)

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_connector", sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("knowledge_connector", "webhook_secret_encrypted")
