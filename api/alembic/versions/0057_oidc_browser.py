"""oidc_login.browser_hash: login preso a um segredo do navegador (Fase 49)

Revision ID: 0057
Revises: 0056
Create Date: 2026-11-12

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # logins em andamento de antes da coluna não têm segredo; vencem em 10 minutos
    op.execute("DELETE FROM oidc_login")
    op.add_column("oidc_login", sa.Column("browser_hash", sa.String(64), nullable=False))
    # e-mail sem diferença de caixa: o SSO acha a conta que o owner cadastrou com maiúscula
    op.create_index("ix_user_account_email_lower", "user_account", [sa.text("lower(email)")])


def downgrade() -> None:
    op.drop_index("ix_user_account_email_lower", table_name="user_account")
    op.drop_column("oidc_login", "browser_hash")
