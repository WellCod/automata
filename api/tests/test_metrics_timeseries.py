"""Série diária do analytics contra Postgres real (agregação por dia em UTC)."""

import os
import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

import pytest
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.repositories.config import ConfigRepository
from app.repositories.run import DailyRunStats, RunRepository
from app.repositories.usage import DailyUsage, UsageRepository
from app.routers.metrics import build_series
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
        command.upgrade(Config("alembic.ini"), "head")
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


def _agent(session: Session, name: str) -> uuid.UUID:
    svc = ConfigService(ConfigRepository(session))
    config = svc.create_config(name, description="")
    svc.save_draft(config.id, ConfigPayload(model_id="gpt-4o"), "tester")
    svc.publish(config.id, "tester")
    return config.id


def _run(
    session: Session, agent: uuid.UUID, at: datetime, status: str = "success", ms: int = 100
) -> None:
    run = RunRepository(session).record(
        agent_config_id=agent, user_id="u", status=status, duration_ms=ms
    )
    run.created_at = at
    session.flush()


def _usage(session: Session, agent: uuid.UUID, at: datetime, tokens: int, cost: float) -> None:
    event = UsageRepository(session).record_event(
        agent_config_id=agent,
        user_id="u",
        model_id="gpt-4o",
        input_tokens=tokens,
        output_tokens=0,
        total_tokens=tokens,
        cost=cost,
    )
    event.created_at = at
    session.flush()


def test_daily_agrupa_por_dia_e_filtra_agente(session: Session) -> None:
    a = _agent(session, "serie-a")
    b = _agent(session, "serie-b")
    d1 = datetime(2026, 3, 10, 23, 30, tzinfo=UTC)
    d2 = datetime(2026, 3, 12, 0, 15, tzinfo=UTC)
    _run(session, a, d1, ms=100)
    _run(session, a, d1 + timedelta(minutes=10), status="error", ms=300)
    _run(session, a, d2, ms=200)
    _run(session, b, d2, ms=900)
    _usage(session, a, d1, 100, 0.01)
    _usage(session, a, d2, 50, 0.02)
    _usage(session, b, d2, 1000, 1.0)
    since = datetime(2026, 3, 10, tzinfo=UTC)
    until = datetime(2026, 3, 12, 23, 59, 59, tzinfo=UTC)

    runs = RunRepository(session).daily(since=since, until=until, config_id=a)
    assert [(r.day, r.total_runs, r.error_count) for r in runs] == [
        (date(2026, 3, 10), 2, 1),
        (date(2026, 3, 12), 1, 0),
    ]
    assert runs[0].p50_ms == pytest.approx(200)

    usage = UsageRepository(session).daily(since=since, until=until, agent_config_id=a)
    assert [(u.day, u.total_tokens) for u in usage] == [
        (date(2026, 3, 10), 100),
        (date(2026, 3, 12), 50),
    ]

    todos = RunRepository(session).daily(since=since, until=until)
    assert [r.total_runs for r in todos] == [2, 2]


def test_build_series_preenche_dias_vazios() -> None:
    first, last = date(2026, 3, 10), date(2026, 3, 12)
    runs = [DailyRunStats(date(2026, 3, 11), 4, 1, 120.0, 900.0)]
    usage = [DailyUsage(date(2026, 3, 12), 300, 0.5)]

    series = build_series(first, last, runs, usage)

    assert [p.date for p in series] == [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)]
    assert series[0].total_runs == 0 and series[0].p50_ms is None and series[0].total_cost is None
    assert series[1].total_runs == 4 and series[1].error_count == 1 and series[1].p95_ms == 900.0
    assert series[2].total_tokens == 300 and series[2].total_cost == 0.5
