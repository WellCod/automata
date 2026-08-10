"""create_user

Revision ID: 0004
Revises: 0002
Create Date: 2026-08-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_account",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(512), nullable=False),
        sa.Column(
            "role",
            sa.Enum("owner", "editor", "viewer", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_account_email", "user_account", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_account_email", table_name="user_account")
    op.drop_table("user_account")
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
