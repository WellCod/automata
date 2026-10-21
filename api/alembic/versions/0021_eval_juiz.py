"""eval_run: modelo do juiz e consumo total da execução (ADR-0015)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("eval_run", sa.Column("judge_model", sa.String(64), nullable=True))
    op.add_column(
        "eval_run", sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0")
    )
    op.add_column("eval_run", sa.Column("cost", sa.Numeric(14, 8), nullable=True))


def downgrade() -> None:
    for column in ("cost", "total_tokens", "judge_model"):
        op.drop_column("eval_run", column)
