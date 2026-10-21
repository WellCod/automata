"""eval_run e eval_result: execuções da suíte; eval_run_id em agent_run e usage_event (ADR-0015)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "eval_run",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("agent_config_id", _UUID, nullable=False),
        sa.Column("version_id", _UUID, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("not_evaluated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("cases", postgresql.JSONB, nullable=False),
        sa.Column("started_by", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agent_config_id"], ["agent_config.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["agent_config_version.id"]),
    )
    op.create_index("ix_eval_run_config_created", "eval_run", ["agent_config_id", "created_at"])
    op.create_index("ix_eval_run_version", "eval_run", ["version_id"])
    op.create_index("ix_eval_run_status", "eval_run", ["status"])

    op.create_table(
        "eval_result",
        sa.Column("id", _UUID, nullable=False),
        sa.Column("eval_run_id", _UUID, nullable=False),
        sa.Column("case_id", _UUID, nullable=True),
        sa.Column("case_name", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("checks", postgresql.JSONB, nullable=False),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("tools_called", postgresql.JSONB, nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["eval_case.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_eval_result_run", "eval_result", ["eval_run_id", "position"])

    for table in ("agent_run", "usage_event"):
        op.add_column(table, sa.Column("eval_run_id", _UUID, nullable=True))
        op.create_foreign_key(
            f"fk_{table}_eval_run", table, "eval_run", ["eval_run_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index(f"ix_{table}_eval_run_id", table, ["eval_run_id"])


def downgrade() -> None:
    for table in ("agent_run", "usage_event"):
        op.drop_index(f"ix_{table}_eval_run_id", table_name=table)
        op.drop_constraint(f"fk_{table}_eval_run", table, type_="foreignkey")
        op.drop_column(table, "eval_run_id")
    op.drop_table("eval_result")
    op.drop_table("eval_run")
