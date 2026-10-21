"""eval_schedule: webhook de aviso de regressão com URL e segredo cifrados (ADR-0018)

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # URL e segredo juntos, cifrados com MCP_SECRETS_KEY: URL de Slack e Teams carrega token
    op.add_column("eval_schedule", sa.Column("webhook_encrypted", sa.Text, nullable=True))
    # só o host aparece no painel
    op.add_column("eval_schedule", sa.Column("webhook_host", sa.String(255), nullable=True))
    op.add_column("eval_schedule", sa.Column("webhook_last_status", sa.String(255), nullable=True))
    op.add_column(
        "eval_schedule", sa.Column("webhook_last_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    for column in ("webhook_last_at", "webhook_last_status", "webhook_host", "webhook_encrypted"):
        op.drop_column("eval_schedule", column)
