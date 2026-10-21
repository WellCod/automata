"""eval_run.trigger e eval_run.target: quem disparou e alvo por apelido (ADR-0016)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # manual | integration | schedule; as execuções da Fase 16 foram todas pelo painel
    op.add_column(
        "eval_run",
        sa.Column("trigger", sa.String(16), nullable=False, server_default="manual"),
    )
    # draft | current quando o alvo veio por apelido; nulo quando veio por version_id
    op.add_column("eval_run", sa.Column("target", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("eval_run", "target")
    op.drop_column("eval_run", "trigger")
