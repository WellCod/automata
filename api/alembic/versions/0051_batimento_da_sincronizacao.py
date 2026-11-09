"""knowledge_connector.sync_heartbeat_at: conector preso em running liberado (Fase 43)

Revision ID: 0051
Revises: 0050
Create Date: 2026-11-09

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_connector",
        sa.Column("sync_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_connector", "sync_heartbeat_at")
