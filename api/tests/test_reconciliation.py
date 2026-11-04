"""Conciliação do custo estimado com o relatório dos provedores (ADR-0037)."""

import os
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx
import pytest
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.reconciliation import fetch_anthropic, fetch_openai, provider_of
from app.settings import get_settings

DAY = date(2026, 11, 2)


def _client(pages: list[dict[str, Any]], seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=pages[len(seen) - 1])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_anthropic_em_centavos_e_paginado() -> None:
    seen: list[httpx.Request] = []
    pages = [
        {
            "data": [
                {
                    "starting_at": "2026-11-02T00:00:00Z",
                    "ending_at": "2026-11-03T00:00:00Z",
                    "results": [{"amount": "123.45", "currency": "USD"}, {"amount": "76.55"}],
                }
            ],
            "has_more": True,
            "next_page": "page_2",
        },
        {
            "data": [{"starting_at": "2026-11-03T00:00:00Z", "results": []}],
            "has_more": False,
            "next_page": None,
        },
    ]
    days = fetch_anthropic("sk-ant-admin-x", DAY, DAY + timedelta(days=2), _client(pages, seen))
    assert days == {DAY: Decimal("2.00"), DAY + timedelta(days=1): Decimal(0)}
    assert seen[0].headers["x-api-key"] == "sk-ant-admin-x"
    assert seen[0].url.params["bucket_width"] == "1d"
    assert seen[1].url.params["page"] == "page_2"


def test_openai_em_dolares() -> None:
    seen: list[httpx.Request] = []
    start = int(datetime(2026, 11, 2, tzinfo=UTC).timestamp())
    pages = [
        {
            "data": [
                {
                    "start_time": start,
                    "end_time": start + 86400,
                    "results": [{"amount": {"value": 0.1308, "currency": "usd"}}],
                }
            ],
            "has_more": False,
        }
    ]
    days = fetch_openai("sk-admin-x", DAY, DAY + timedelta(days=1), _client(pages, seen))
    assert days == {DAY: Decimal("0.1308")}
    assert seen[0].headers["authorization"] == "Bearer sk-admin-x"
    assert seen[0].url.params["start_time"] == str(start)


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("claude-haiku-4-5", "anthropic"),
        ("gpt-4o-mini", "openai"),
        ("o3-mini", "openai"),
        ("text-embedding-3-small", "openai"),
        ("voyage-3.5", None),
        ("cohere:rerank-v3.5", None),
    ],
)
def test_provedor_pelo_modelo(model: str, provider: str | None) -> None:
    assert provider_of(model) == provider


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def test_compara_informado_com_estimado_e_avisa_uma_vez(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.alerts as alerts
    import app.reconciliation as rec
    from app.db import get_engine
    from app.models.config import AgentConfig
    from app.models.embedding_usage import EmbeddingUsage
    from app.models.usage import UsageEvent

    now = datetime(2026, 11, 4, 12, tzinfo=UTC)
    closed = date(2026, 11, 3)
    agent_id = uuid4()
    with Session(get_engine()) as session:
        session.add(AgentConfig(id=agent_id, name="conciliado", description="x", kind="agent"))
        session.flush()

        def usage(model: str, cost: str, when: datetime) -> UsageEvent:
            return UsageEvent(
                agent_config_id=agent_id,
                user_id="u",
                model_id=model,
                period="202611",
                cost=Decimal(cost),
                created_at=when,
            )

        session.add_all(
            [
                usage("claude-haiku-4-5", "6.00", datetime(2026, 11, 3, 10, tzinfo=UTC)),
                usage("claude-haiku-4-5", "1.00", datetime(2026, 11, 4, 9, tzinfo=UTC)),
                usage("gpt-4o-mini", "0.50", datetime(2026, 11, 3, 10, tzinfo=UTC)),
                EmbeddingUsage(
                    kind="search",
                    model="text-embedding-3-small",
                    period="202611",
                    tokens=10,
                    cost=Decimal("0.50"),
                    created_at=datetime(2026, 11, 3, 11, tzinfo=UTC),
                ),
            ]
        )
        session.commit()

    monkeypatch.setenv("ANTHROPIC_ADMIN_KEY", "sk-ant-admin-x")
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "sk-admin-x")
    monkeypatch.setattr(
        rec,
        "FETCHERS",
        {
            "anthropic": lambda k, s, e, c: {closed: Decimal("10"), now.date(): Decimal("1")},
            "openai": lambda k, s, e, c: {closed: Decimal("1.05")},
        },
    )
    assert rec.refresh(now) == {"anthropic": 2, "openai": 1}

    with Session(get_engine()) as session:
        rows = {(r["provider"], r["day"]): r for r in rec.report(session, 7, now.date())}
    anthropic = rows[("anthropic", closed)]
    assert (anthropic["reported_usd"], anthropic["estimated_usd"]) == (10.0, 6.0)
    assert anthropic["diff_percent"] == 40.0 and anthropic["closed"] is True
    # o embedding da OpenAI entra no estimado do provedor
    assert rows[("openai", closed)]["estimated_usd"] == 1.0
    assert rows[("anthropic", now.date())]["closed"] is False

    sent: list[str] = []
    monkeypatch.setattr(alerts, "destinations_for", lambda s, e: [object()])
    monkeypatch.setattr(alerts, "broadcast", lambda s, e, d, t: sent.append(t) or 1)
    monkeypatch.setattr(rec, "_last_fetch", None)
    with Session(get_engine()) as session:
        first = rec.check_divergence(session, now)
        second = rec.check_divergence(session, now)
    # só o dia fechado da Anthropic passa de 20%; a OpenAI ficou em 4,8%
    assert first == [("anthropic", closed)] and second == []
    assert "US$ 10.00" in sent[0] and "+40.0%" in sent[0]
