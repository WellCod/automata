"""alert_destination: tipo e-mail com até 5 endereços (ADR-0037)

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "alert_destination",
        sa.Column("kind", sa.String(16), nullable=False, server_default="webhook"),
    )
    op.add_column("alert_destination", sa.Column("email_to", JSONB(), nullable=True))
    op.alter_column("alert_destination", "webhook_encrypted", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM alert_destination WHERE kind = 'email'")
    op.alter_column("alert_destination", "webhook_encrypted", nullable=False)
    op.drop_column("alert_destination", "email_to")
    op.drop_column("alert_destination", "kind")
