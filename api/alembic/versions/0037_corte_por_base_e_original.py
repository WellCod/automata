"""knowledge_base.chunking e knowledge_content_original (ADR-0029)

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vazio = recursiva com sobreposição de 10%, o corte de antes desta fase
    op.add_column(
        "knowledge_base",
        sa.Column("chunking", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    # original de arquivo e texto, para reprocessar com outro corte; URL e conector baixam de novo
    op.create_table(
        "knowledge_content_original",
        sa.Column(
            "content_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_content.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_content_original")
    op.drop_column("knowledge_base", "chunking")
