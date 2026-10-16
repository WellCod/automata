"""create_revoked_token

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_token",
        sa.Column("jti", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("jti"),
    )
    op.create_index("ix_revoked_token_expires_at", "revoked_token", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_revoked_token_expires_at", table_name="revoked_token")
    op.drop_table("revoked_token")
