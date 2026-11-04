"""data_subject_request.source: quem pediu, owner, integração ou o próprio (ADR-0036)

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "data_subject_request",
        sa.Column("source", sa.String(16), nullable=False, server_default="panel"),
    )


def downgrade() -> None:
    op.drop_column("data_subject_request", "source")
