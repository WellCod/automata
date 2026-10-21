"""knowledge_base.retrieval: estratégia de busca da base, com reranker e HyDE (ADR-0017)

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vazio = busca de antes, sem reranker nem HyDE
    op.add_column(
        "knowledge_base",
        sa.Column("retrieval", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("knowledge_base", "retrieval")
