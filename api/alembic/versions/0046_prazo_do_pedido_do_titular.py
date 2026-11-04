"""data_subject_request: prazo legal e avisos de falha e de vencimento (ADR-0036)

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for column in ("due_at", "failed_alerted_at", "due_alerted_at"):
        op.add_column(
            "data_subject_request", sa.Column(column, sa.DateTime(timezone=True), nullable=True)
        )
    # pedidos de antes da fase ganham o prazo contado da criação
    op.execute(
        "UPDATE data_subject_request SET due_at = created_at + interval '15 days' "
        "WHERE due_at IS NULL"
    )


def downgrade() -> None:
    for column in ("due_alerted_at", "failed_alerted_at", "due_at"):
        op.drop_column("data_subject_request", column)
