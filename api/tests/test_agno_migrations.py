"""Migração das tabelas do Agno no entrypoint: banco novo e segunda rodada sem efeito."""

import os
from collections.abc import Generator

import pytest
from agno.db.postgres import PostgresDb
from agno.session.agent import AgentSession
from testcontainers.postgres import PostgresContainer

from app import agno_migrations
from app.settings import get_settings


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        yield url
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_banco_novo_migra_e_segunda_rodada_nao_muda_nada(db_url: str) -> None:
    agno_migrations.migrate()
    db = PostgresDb(db_url=db_url)
    session = AgentSession(session_id="s1", agent_id="a1", user_id="u1", created_at=1)
    db.upsert_session(session)

    agno_migrations.migrate()

    stored = db.get_session(session_id="s1", user_id="u1")
    assert stored is not None and stored.session_id == "s1"
