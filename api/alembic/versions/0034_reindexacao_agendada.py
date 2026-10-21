"""sincronização agendada de conector e reindexação agendada de URL (ADR-0024)

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vazio = só manual
    op.add_column("knowledge_connector", sa.Column("sync_every_hours", sa.Integer, nullable=True))
    op.add_column(
        "knowledge_connector",
        sa.Column("next_sync_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_connector_next_sync_at", "knowledge_connector", ["next_sync_at"])
    op.add_column("knowledge_content", sa.Column("refresh_every_hours", sa.Integer, nullable=True))
    op.add_column(
        "knowledge_content",
        sa.Column("next_refresh_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_content_next_refresh_at", "knowledge_content", ["next_refresh_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_content_next_refresh_at", table_name="knowledge_content")
    op.drop_index("ix_knowledge_connector_next_sync_at", table_name="knowledge_connector")
    op.drop_column("knowledge_content", "next_refresh_at")
    op.drop_column("knowledge_content", "refresh_every_hours")
    op.drop_column("knowledge_connector", "next_sync_at")
    op.drop_column("knowledge_connector", "sync_every_hours")
