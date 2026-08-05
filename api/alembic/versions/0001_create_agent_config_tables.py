"""create_agent_config_tables

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("draft_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_config_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "published", name="configpayloadstatus"),
            nullable=False,
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["config_id"], ["agent_config.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_foreign_key(
        "fk_current_version",
        "agent_config",
        "agent_config_version",
        ["current_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_draft_version",
        "agent_config",
        "agent_config_version",
        ["draft_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_draft_version", "agent_config", type_="foreignkey")
    op.drop_constraint("fk_current_version", "agent_config", type_="foreignkey")
    op.drop_table("agent_config_version")
    op.drop_table("agent_config")
    op.execute("DROP TYPE IF EXISTS configpayloadstatus")
