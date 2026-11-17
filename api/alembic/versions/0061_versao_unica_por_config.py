"""número de versão único por config (OPS-11)

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX = "ix_agent_config_version_config_id_version_number"


def upgrade() -> None:
    conn = op.get_bind()
    # dois editores salvando juntos podiam gravar o mesmo número: o repetido vai para o fim
    duplicated = conn.execute(
        sa.text(
            "SELECT id, config_id FROM ("
            " SELECT id, config_id, row_number() OVER ("
            "  PARTITION BY config_id, version_number ORDER BY created_at, id) AS n"
            " FROM agent_config_version) t WHERE n > 1"
        )
    ).all()
    for version_id, config_id in duplicated:
        conn.execute(
            sa.text(
                "UPDATE agent_config_version SET version_number = ("
                " SELECT max(version_number) + 1 FROM agent_config_version WHERE config_id = :c)"
                " WHERE id = :v"
            ),
            {"c": config_id, "v": version_id},
        )
    op.drop_index(INDEX, table_name="agent_config_version")
    op.create_index(INDEX, "agent_config_version", ["config_id", "version_number"], unique=True)


def downgrade() -> None:
    op.drop_index(INDEX, table_name="agent_config_version")
    op.create_index(INDEX, "agent_config_version", ["config_id", "version_number"])
