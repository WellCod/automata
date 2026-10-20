"""Reset completo da demo — apaga todos os dados e re-executa o seed demo."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.seed import seed_demo

_TABLES = [
    "embedding_usage",
    "knowledge_content",
    "knowledge_base",
    "eval_result",
    "eval_run",
    "eval_case",
    "usage_event",
    "agent_run",
    "agent_config_version",
    "agent_config",
    "mcp_server",
    "integration_token",
    "user_account",
]

# Tabelas de dados do Agno (schema "ai" do PostgresDb). Ficam de fora a de
# versão do schema e as de credenciais/OAuth do próprio AgentOS.
_AGNO_SCHEMA = "ai"
_AGNO_TABLES = [
    "agno_sessions",
    "agno_memories",
    "agno_metrics",
    "agno_eval_runs",
    "agno_knowledge",
    "agno_culture",
    "agno_traces",
    "agno_spans",
    "agno_learnings",
    "agno_approvals",
    "agno_schedule_runs",
    "agno_schedules",
]


def truncate_all(engine: Engine) -> list[str]:
    """Trunca as tabelas da aplicação e as do Agno que existirem; devolve as truncadas."""
    with engine.connect() as conn:
        # O Agno cria as tabelas sob demanda: só entram as que já existem
        existing = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name = ANY(:names)"
            ),
            {"schema": _AGNO_SCHEMA, "names": _AGNO_TABLES},
        ).scalars()
        tables = _TABLES + [f'{_AGNO_SCHEMA}."{name}"' for name in sorted(existing)]
        conn.execute(text(f"TRUNCATE TABLE {', '.join(tables)} CASCADE"))
        # vetores das bases de conhecimento: uma tabela por base, criada pelo Agno
        vector_tables = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema AND table_name LIKE 'kb!_%' ESCAPE '!'"
            ),
            {"schema": _AGNO_SCHEMA},
        ).scalars()
        for name in sorted(vector_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS {_AGNO_SCHEMA}."{name}"'))
            tables.append(f'{_AGNO_SCHEMA}."{name}"')
        conn.commit()
    return tables


def main() -> None:
    for var in ("SEED_OWNER_EMAIL", "SEED_OWNER_PASSWORD"):
        if not os.environ.get(var):
            print(f"variável obrigatória ausente: {var}")
            sys.exit(1)

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://automata:automata@localhost:5432/automata"
    )
    engine = create_engine(db_url)

    tables = truncate_all(engine)
    print(f"tabelas truncadas: {len(tables)}")

    with Session(engine) as session:
        seed_demo(session)
    print("reset concluído")


if __name__ == "__main__":
    main()
