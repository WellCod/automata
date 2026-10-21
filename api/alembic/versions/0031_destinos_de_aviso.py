"""alert_destination e alert_sent: avisos da instância (ADR-0021)

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_destination",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        # URL e segredo juntos, cifrados com MCP_SECRETS_KEY, como o webhook da suíte
        sa.Column("webhook_encrypted", sa.Text, nullable=False),
        sa.Column("webhook_host", sa.String(255), nullable=False),
        sa.Column("events", postgresql.JSONB, nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("last_status", sa.String(255), nullable=True),
        sa.Column("last_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # um aviso por config, evento e janela (mês do orçamento, hora do pico de erro);
    # a chave única faz duas réplicas não mandarem o mesmo aviso
    op.create_table(
        "alert_sent",
        sa.Column(
            "agent_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent_config.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("event", sa.String(32), primary_key=True),
        sa.Column("window", sa.String(16), primary_key=True),
        sa.Column(
            "sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("alert_sent")
    op.drop_table("alert_destination")
