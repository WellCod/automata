"""Seed de instância. Uso: uv run python scripts/seed.py [minimal|demo]"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.seed import seed_demo, seed_minimal

logging.basicConfig(level=logging.INFO, format="%(message)s")

_SETS = {"minimal": seed_minimal, "demo": seed_demo}


def main() -> None:
    seed_set = sys.argv[1] if len(sys.argv) > 1 else "minimal"
    if seed_set not in _SETS:
        print(f"uso: uv run python scripts/seed.py [{'|'.join(_SETS)}]")
        sys.exit(1)

    for var in ("SEED_OWNER_EMAIL", "SEED_OWNER_PASSWORD"):
        if not os.environ.get(var):
            print(f"variável de ambiente obrigatória ausente: {var}")
            sys.exit(1)

    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://automata:automata@localhost:5432/automata"
    )
    engine = create_engine(db_url)

    with Session(engine) as session:
        _SETS[seed_set](session)


if __name__ == "__main__":
    main()
