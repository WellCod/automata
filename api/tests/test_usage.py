"""Testes de registro e rollup de consumo.

Usa testcontainers para rodar contra Postgres real — as invariantes de
agregação não podem ser testadas com mocks.
"""

import os
import uuid
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.repositories.config import ConfigRepository
from app.repositories.usage import UsageRepository
from app.schemas.config import ConfigPayload
from app.services.config import ConfigService
from app.settings import get_settings


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "pk")
        os.environ.setdefault("JWT_PUBLIC_KEY", "pub")
        get_settings.cache_clear()
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def session(db_url: str) -> Generator[Session, None, None]:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(bind=conn) as sess:
            yield sess
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def agent_id(session: Session) -> uuid.UUID:
    repo = ConfigRepository(session)
    svc = ConfigService(repo)
    config = svc.create_config("agente-metering")
    svc.save_draft(config.id, ConfigPayload(model_id="gpt-4o"), "tester")
    svc.publish(config.id, "tester")
    return config.id


def _period() -> str:
    return datetime.now(UTC).strftime("%Y%m")


# --- UsageRepository ---


def test_record_event_persiste(session: Session, agent_id: uuid.UUID) -> None:
    repo = UsageRepository(session)
    event = repo.record_event(
        agent_config_id=agent_id,
        user_id="u1",
        model_id="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        period=_period(),
    )
    assert event.id is not None
    assert event.total_tokens == 150


def test_rollup_soma_tokens(session: Session, agent_id: uuid.UUID) -> None:
    repo = UsageRepository(session)
    period = _period()
    repo.record_event(
        agent_config_id=agent_id,
        user_id="u1",
        model_id="gpt-4o",
        input_tokens=200,
        output_tokens=100,
        total_tokens=300,
        period=period,
    )
    repo.record_event(
        agent_config_id=agent_id,
        user_id="u2",
        model_id="gpt-4o",
        input_tokens=50,
        output_tokens=25,
        total_tokens=75,
        period=period,
    )

    rows = repo.rollup(period=period, agent_config_id=agent_id)
    assert len(rows) == 1
    r = rows[0]
    assert r.run_count == 2
    assert r.input_tokens == 250
    assert r.total_tokens == 375


def test_rollup_sem_eventos_retorna_vazio(session: Session) -> None:
    repo = UsageRepository(session)
    rows = repo.rollup(period="199901")
    assert rows == []


def test_rollup_filtra_por_periodo(session: Session, agent_id: uuid.UUID) -> None:
    repo = UsageRepository(session)
    repo.record_event(
        agent_config_id=agent_id,
        user_id="u1",
        model_id="gpt-4o",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        period="202501",
    )
    rows = repo.rollup(period="202501", agent_config_id=agent_id)
    assert len(rows) == 1
    rows_other = repo.rollup(period="202502", agent_config_id=agent_id)
    assert len(rows_other) == 0


def test_rollup_cost_acumulado(session: Session, agent_id: uuid.UUID) -> None:
    repo = UsageRepository(session)
    period = "203001"
    repo.record_event(
        agent_config_id=agent_id,
        user_id="u1",
        model_id="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost=0.001,
        period=period,
    )
    repo.record_event(
        agent_config_id=agent_id,
        user_id="u1",
        model_id="gpt-4o",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cost=0.002,
        period=period,
    )
    rows = repo.rollup(period=period, agent_config_id=agent_id)
    assert rows[0].cost is not None
    assert abs(rows[0].cost - 0.003) < 1e-6


# --- endpoint ---


def test_endpoint_rollup_retorna_lista(db_url: str, agent_id: uuid.UUID) -> None:
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()

    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
    response = client.get(f"/api/v1/usage/rollup?period={_period()}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_endpoint_rollup_periodo_padrao(db_url: str) -> None:
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()

    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False, enable_auth=False))
    response = client.get("/api/v1/usage/rollup")
    assert response.status_code == 200
