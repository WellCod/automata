"""Garante que o autogenerate do Alembic não emite DROP para tabelas do AgentOS.

O footgun: auto_provision_dbs=True faz o AgentOS criar suas tabelas no boot.
Se include_object não filtrar essas tabelas, a próxima `alembic revision
--autogenerate` vai emitir DROP TABLE para todas elas.
"""

import os
from collections.abc import Generator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine
from testcontainers.postgres import PostgresContainer

from app.models import Base


@pytest.fixture(scope="module")
def postgres_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:17") as pg:
        yield pg.get_connection_url().replace("psycopg2", "psycopg")


@pytest.fixture(scope="module")
def migrated_db(postgres_url: str) -> Generator[str, None, None]:
    os.environ["DATABASE_URL"] = postgres_url

    engine = create_engine(postgres_url)

    # Provisiona tabelas do AgentOS
    from agno.db.postgres import PostgresDb
    from agno.os import AgentOS
    from fastapi.testclient import TestClient

    db = PostgresDb(db_url=postgres_url)
    agent_os = AgentOS(id="test-isolation", db=db, auto_provision_dbs=True)
    with TestClient(agent_os.get_app()):
        pass

    # Roda nossas migrations
    from alembic import command

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    yield postgres_url

    engine.dispose()
    os.environ.pop("DATABASE_URL", None)


def test_autogenerate_vazio_com_tabelas_do_agentos(migrated_db: str) -> None:
    """Após rodar nossas migrations num banco que já tem as tabelas do AgentOS,
    o autogenerate não deve detectar diferença alguma."""
    engine = create_engine(migrated_db)
    with engine.connect() as conn:
        mc = MigrationContext.configure(
            conn,
            opts={"include_object": _include_object},
        )
        diff = compare_metadata(mc, Base.metadata)

    assert diff == [], f"Migrations pendentes detectadas: {diff}"

    engine.dispose()


def _include_object(
    object: object, name: str, type_: str, reflected: bool, compare_to: object
) -> bool:
    if type_ == "table":
        return name in set(Base.metadata.tables.keys())
    return True
