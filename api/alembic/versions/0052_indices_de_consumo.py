"""índices de consumo e de execuções (Fase 44)

- `usage_event.run_id`: o consumo das etapas filhas do workflow faz join por ele.
- `(period, agent_config_id)` e `(user_id, period)` passam a levar o `cost`: a soma do
  orçamento sai só do índice, sem ir ao heap.
- `(agent_config_id, created_at)` parcial nas conversas (`eval_run_id IS NULL`): a lista
  de execuções e as métricas por agente filtram assim.
- `embedding_usage.base_id` com `tokens` e `cost`: a lista de bases soma o histórico.

Criados com CONCURRENTLY, fora da transação, para não travar escrita em tabela grande.

Revision ID: 0052
Revises: 0051
Create Date: 2026-11-09

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE = [
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usage_event_run_id ON usage_event (run_id)",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usage_event_period_config_cost "
    "ON usage_event (period, agent_config_id) INCLUDE (cost)",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usage_event_user_period_cost "
    "ON usage_event (user_id, period) INCLUDE (cost)",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_agent_run_config_conversation "
    "ON agent_run (agent_config_id, created_at) WHERE eval_run_id IS NULL",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_embedding_usage_base_cost "
    "ON embedding_usage (base_id) INCLUDE (tokens, cost)",
]
# substituídos pelos que levam o custo
DROP = [
    "ix_usage_event_period_agent_config_id",
    "ix_usage_event_user_period",
    "ix_embedding_usage_base",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for sql in CREATE:
            op.execute(sql)
        for name in DROP:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usage_event_period_agent_config_id "
            "ON usage_event (period, agent_config_id)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_usage_event_user_period "
            "ON usage_event (user_id, period)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_embedding_usage_base "
            "ON embedding_usage (base_id)"
        )
        for name in (
            "ix_usage_event_run_id",
            "ix_usage_event_period_config_cost",
            "ix_usage_event_user_period_cost",
            "ix_agent_run_config_conversation",
            "ix_embedding_usage_base_cost",
        ):
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
