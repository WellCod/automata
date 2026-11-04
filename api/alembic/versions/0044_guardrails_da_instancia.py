"""instance_guardrails: piso de guardrails da instância (ADR-0034)

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instance_guardrails",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("settings", JSONB(), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("instance_guardrails")
