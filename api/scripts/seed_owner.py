"""Cria o primeiro usuário owner. Uso: uv run python scripts/seed_owner.py EMAIL SENHA"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.services.user import UserService


def main() -> None:
    if len(sys.argv) != 3:
        print("uso: uv run python scripts/seed_owner.py EMAIL SENHA")
        sys.exit(1)

    email, password = sys.argv[1], sys.argv[2]
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://automata:automata@localhost:5432/automata"
    )

    engine = create_engine(db_url)
    with Session(engine) as session:
        svc = UserService(UserRepository(session))
        try:
            user = svc.create_user(email=email, password=password, role=UserRole.owner)
            session.commit()
            print(f"owner criado: {user.email}")
        except ValueError as e:
            print(f"erro: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
