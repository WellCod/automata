"""add_indexes

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-12

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # agent_config_version: FK sem índice nativo + queries que ordenam por version_number
    op.create_index(
        "ix_agent_config_version_config_id_version_number",
        "agent_config_version",
        ["config_id", "version_number"],
    )
    # agent_config: list_configs ordena por updated_at DESC
    op.create_index(
        "ix_agent_config_updated_at",
        "agent_config",
        ["updated_at"],
    )
    # usage_event: rollup filtra por period (obrigatório) e agent_config_id (opcional)
    op.create_index(
        "ix_usage_event_period_agent_config_id",
        "usage_event",
        ["period", "agent_config_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_event_period_agent_config_id", table_name="usage_event")
    op.drop_index("ix_agent_config_updated_at", table_name="agent_config")
    op.drop_index(
        "ix_agent_config_version_config_id_version_number",
        table_name="agent_config_version",
    )
