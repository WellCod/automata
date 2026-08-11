"""Reset completo da demo — apaga todos os dados e re-executa o seed demo."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.seed import seed_demo

_TABLES = ["usage_event", "agent_config_version", "agent_config", "user_account"]


def main() -> None:
    for var in ("SEED_OWNER_EMAIL", "SEED_OWNER_PASSWORD"):
        if not os.environ.get(var):
            print(f"variável obrigatória ausente: {var}")
            sys.exit(1)

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://automata:automata@localhost:5432/automata"
    )
    engine = create_engine(db_url)

    with engine.connect() as conn:
        tables = ", ".join(_TABLES)
        conn.execute(text(f"TRUNCATE TABLE {tables} CASCADE"))
        conn.commit()
    print("tabelas truncadas")

    with Session(engine) as session:
        seed_demo(session)
    print("reset concluído")


if __name__ == "__main__":
    main()
