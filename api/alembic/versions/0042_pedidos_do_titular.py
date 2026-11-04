"""data_subject_request: exportação e exclusão por titular (ADR-0032)

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_subject_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("subject_hash", sa.String(64), nullable=False),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("counts", JSONB, nullable=True),
        sa.Column("result", sa.LargeBinary, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_data_subject_request_subject_hash", "data_subject_request", ["subject_hash"]
    )
    # a consulta e a exclusão procuram o titular nos runs registrados
    op.create_index("ix_agent_run_user_id", "agent_run", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_user_id", table_name="agent_run")
    op.drop_index("ix_data_subject_request_subject_hash", table_name="data_subject_request")
    op.drop_table("data_subject_request")
