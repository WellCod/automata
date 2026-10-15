"""kind do config: agente ou time

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # configs existentes são todos agentes (ADR-0011)
    op.add_column(
        "agent_config",
        sa.Column("kind", sa.String(16), nullable=False, server_default="agent"),
    )
    op.create_index("ix_agent_config_kind", "agent_config", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_agent_config_kind", table_name="agent_config")
    op.drop_column("agent_config", "kind")
