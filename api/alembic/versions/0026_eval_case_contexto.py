"""eval_case.context: mensagens anteriores rodadas na mesma sessão do caso (ADR-0016)

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "eval_case",
        sa.Column("context", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("eval_case", "context")
