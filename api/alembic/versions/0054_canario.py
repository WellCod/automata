"""canário por config e versão no run (ADR-0040)

Revision ID: 0054
Revises: 0053
Create Date: 2026-11-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_config", sa.Column("canary_version_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_canary_version",
        "agent_config",
        "agent_config_version",
        ["canary_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("agent_config", sa.Column("canary_percent", sa.Integer(), nullable=True))
    op.add_column(
        "agent_config", sa.Column("canary_started_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("agent_run", sa.Column("version_id", UUID(as_uuid=True), nullable=True))
    op.create_index("ix_agent_run_version_created", "agent_run", ["version_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_version_created", table_name="agent_run")
    op.drop_column("agent_run", "version_id")
    op.drop_column("agent_config", "canary_started_at")
    op.drop_column("agent_config", "canary_percent")
    op.drop_constraint("fk_canary_version", "agent_config", type_="foreignkey")
    op.drop_column("agent_config", "canary_version_id")
