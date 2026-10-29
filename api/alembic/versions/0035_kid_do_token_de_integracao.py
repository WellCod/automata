"""integration_token.signing_kid: chave que assinou o token (ADR-0026)

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vazio = emitido antes do kid; conta como chave antiga no estado da rotação
    op.add_column("integration_token", sa.Column("signing_kid", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("integration_token", "signing_kid")
