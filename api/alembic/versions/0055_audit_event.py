"""audit_event: trilha de auditoria (ADR-0041)

Revision ID: 0055
Revises: 0054
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("actor", sa.String(128), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("config_id", UUID(as_uuid=True), nullable=True),
        sa.Column("params", JSONB, nullable=True),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
    )
    op.create_index("ix_audit_event_created", "audit_event", ["created_at"])
    op.create_index("ix_audit_event_actor_created", "audit_event", ["actor", "created_at"])
    op.create_index("ix_audit_event_config_created", "audit_event", ["config_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_event")
