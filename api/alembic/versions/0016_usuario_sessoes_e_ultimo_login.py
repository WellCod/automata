"""usuario_sessoes_e_ultimo_login

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_account", sa.Column("tokens_valid_after", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "user_account", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("user_account", "last_login_at")
    op.drop_column("user_account", "tokens_valid_after")
