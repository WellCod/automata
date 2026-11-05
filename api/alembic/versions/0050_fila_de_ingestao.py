"""ingest_job: fila do worker de ingestão separado (ADR-0039)

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingest_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target_id", UUID(as_uuid=True), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingest_job_status_created", "ingest_job", ["status", "created_at"])
    op.create_index("ix_ingest_job_target_id", "ingest_job", ["target_id"])


def downgrade() -> None:
    op.drop_table("ingest_job")
