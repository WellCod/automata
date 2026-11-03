"""knowledge_content.suspect_chunks: trechos com instrução embutida (ADR-0030)

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # conteúdo já indexado fica com 0 até a próxima ingestão ou reprocessamento
    op.add_column(
        "knowledge_content",
        sa.Column("suspect_chunks", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("knowledge_content", "suspect_chunks")
