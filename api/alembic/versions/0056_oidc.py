"""login por oidc: conta pelo sujeito do provedor e login em andamento (ADR-0042)

Revision ID: 0056
Revises: 0055
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # conta criada pelo SSO não tem senha
    op.alter_column("user_account", "hashed_password", nullable=True)
    op.add_column("user_account", sa.Column("sso_issuer", sa.String(512), nullable=True))
    op.add_column("user_account", sa.Column("sso_subject", sa.String(255), nullable=True))
    op.create_unique_constraint(
        "uq_user_account_sso", "user_account", ["sso_issuer", "sso_subject"]
    )
    op.create_table(
        "oidc_login",
        sa.Column("state", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("oidc_login")
    op.drop_constraint("uq_user_account_sso", "user_account", type_="unique")
    op.drop_column("user_account", "sso_subject")
    op.drop_column("user_account", "sso_issuer")
    op.execute("UPDATE user_account SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column("user_account", "hashed_password", nullable=False)
