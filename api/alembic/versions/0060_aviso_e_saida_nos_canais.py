"""aviso de primeiro contato e palavras de saída nos canais (ADR-0045)

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-16

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WELCOME = (
    "Olá! Você está falando com um assistente automático, com inteligência artificial. "
    "As mensagens desta conversa são guardadas para o atendimento. Para falar com uma "
    "pessoa, peça um atendente. Para encerrar e apagar seus dados, envie SAIR."
)
EXIT = ["sair", "apagar meus dados"]


def upgrade() -> None:
    # canal já em uso também passa a avisar: é o que falta para o titular saber com quem fala
    op.add_column(
        "channel",
        sa.Column("welcome_message", sa.String(1000), nullable=False, server_default=WELCOME),
    )
    op.add_column(
        "channel",
        sa.Column(
            "exit_keywords",
            JSONB(),
            nullable=False,
            server_default=sa.text(f"'{json.dumps(EXIT)}'"),
        ),
    )
    op.add_column(
        "channel_conversation",
        sa.Column("welcomed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channel_conversation", "welcomed_at")
    op.drop_column("channel", "exit_keywords")
    op.drop_column("channel", "welcome_message")
