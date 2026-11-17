"""Cria o primeiro usuário owner.

Uso: SEED_OWNER_EMAIL=... SEED_OWNER_PASSWORD=... python scripts/seed_owner.py
(ou EMAIL SENHA como argumentos). SEED_OWNER_MUST_CHANGE=true deixa a senha provisória.
"""

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
    # pelo ambiente a senha não aparece na lista de processos
    if len(sys.argv) == 3:
        email, password = sys.argv[1], sys.argv[2]
    else:
        email = os.environ.get("SEED_OWNER_EMAIL", "")
        password = os.environ.get("SEED_OWNER_PASSWORD", "")
    if not email or not password:
        print("uso: SEED_OWNER_EMAIL=... SEED_OWNER_PASSWORD=... python scripts/seed_owner.py")
        sys.exit(1)
    must_change = os.environ.get("SEED_OWNER_MUST_CHANGE", "").lower() == "true"
    db_url = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://automata:automata@localhost:5432/automata"
    )

    engine = create_engine(db_url)
    with Session(engine) as session:
        svc = UserService(UserRepository(session))
        try:
            user = svc.create_user(
                email=email, password=password, role=UserRole.owner, must_change=must_change
            )
            session.commit()
            print(f"owner criado: {user.email}")
        except ValueError as e:
            print(f"erro: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
