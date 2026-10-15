"""indices de runs e consumo por data e run_id

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-15

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # analytics global filtra só por data; o upsert do tracking busca por run_id
    op.create_index("ix_agent_run_created_at", "agent_run", ["created_at"])
    op.create_index("ix_agent_run_run_id", "agent_run", ["run_id"])
    op.create_index("ix_usage_event_created_at", "usage_event", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_event_created_at", table_name="usage_event")
    op.drop_index("ix_agent_run_run_id", table_name="agent_run")
    op.drop_index("ix_agent_run_created_at", table_name="agent_run")
