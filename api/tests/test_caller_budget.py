"""Orçamento mensal por quem chama (ADR-0031): bloqueio, cadastro e aviso."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.settings import get_settings


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


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app

    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    model = ReplayModel(id="claude-haiku-4-5")
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _agent(client: TestClient, nome: str) -> str:
    created = client.post("/api/v1/configs", json={"name": nome, "description": "x"})
    config_id = str(created.json()["id"])
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": nome, "description": "x", "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _token(name: str) -> str:
    from app.db import get_engine
    from app.models.integration import IntegrationToken

    token_id = uuid4()
    with Session(get_engine()) as session:
        session.add(
            IntegrationToken(
                id=token_id,
                name=name,
                jti=uuid4().hex,
                created_by="owner",
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
        session.commit()
    return f"integration:{token_id}"


def _spend(config_id: str, subject: str, cost: float) -> None:
    from app.budget import current_period
    from app.db import get_engine
    from app.repositories.usage import UsageRepository

    with Session(get_engine()) as session:
        UsageRepository(session).record_event(
            agent_config_id=config_id,  # type: ignore[arg-type]
            user_id=subject,
            model_id="claude-haiku-4-5",
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            cost=cost,
            period=current_period(),
        )
        session.commit()


def _last_run(config_id: str) -> Any:
    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        return session.scalars(
            select(AgentRun)
            .where(AgentRun.agent_config_id == config_id)
            .order_by(AgentRun.created_at.desc())
        ).first()


def test_token_estourado_bloqueia_so_ele(client: TestClient) -> None:
    from app.caller_budget import CALLER_BUDGET_MESSAGE

    agent_id = _agent(client, "pedidos")
    gastador, outro = _token("loja"), _token("app")
    _spend(agent_id, gastador, 2.0)
    resp = client.put(
        f"/api/v1/caller-budgets/{gastador}", json={"monthly_usd": 1.0, "hard_stop": True}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["label"], body["kind"], body["level"]) == ("loja", "integration", "exceeded")

    blocked = client.post(
        f"/agents/{agent_id}/runs",
        data={"message": "oi", "stream": "false", "user_id": gastador},
    )
    assert blocked.json()["content"] == CALLER_BUDGET_MESSAGE
    run = _last_run(agent_id)
    assert (run.status, run.blocked_by) == ("blocked", "budget_exceeded")
    assert run.block_detail["scope"] == "caller"

    client.post(
        f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "false", "user_id": outro}
    )
    assert _last_run(agent_id).status == "success"


def test_sem_bloqueio_so_mede(client: TestClient) -> None:
    agent_id = _agent(client, "medido")
    subject = _token("medido")
    _spend(agent_id, subject, 5.0)
    client.put(f"/api/v1/caller-budgets/{subject}", json={"monthly_usd": 1.0})
    client.post(
        f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "false", "user_id": subject}
    )
    assert _last_run(agent_id).status == "success"
    [listed] = [b for b in client.get("/api/v1/caller-budgets").json() if b["subject"] == subject]
    assert listed["spent_usd"] == 5.0 and listed["percent"] == 500.0


def test_sujeito_desconhecido_e_remocao(client: TestClient) -> None:
    resp = client.put(
        "/api/v1/caller-budgets/integration:00000000-0000-0000-0000-000000000000",
        json={"monthly_usd": 1.0},
    )
    assert resp.status_code == 404
    assert client.put("/api/v1/caller-budgets/qualquer", json={"monthly_usd": 1}).status_code == 404
    subject = _token("removivel")
    client.put(f"/api/v1/caller-budgets/{subject}", json={"monthly_usd": 1.0}).raise_for_status()
    assert client.delete(f"/api/v1/caller-budgets/{subject}").status_code == 204
    assert client.delete(f"/api/v1/caller-budgets/{subject}").status_code == 404


def test_aviso_sai_uma_vez_por_mes(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.alerts as alerts
    from app.caller_budget import CALLER_EXCEEDED, CALLER_WARNING, check_caller_budgets
    from app.db import get_engine
    from app.models.alert import AlertDestination

    sent: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(alerts, "broadcast", lambda s, e, d, t: sent.append((e, d)) or 1)
    with Session(get_engine()) as session:
        session.add(
            AlertDestination(
                name="ops",
                webhook_encrypted="x",
                webhook_host="exemplo.com",
                events=[CALLER_WARNING, CALLER_EXCEEDED],
                created_by="owner",
            )
        )
        session.commit()
    agent_id = _agent(client, "avisado")
    subject = _token("avisado")
    client.put(f"/api/v1/caller-budgets/{subject}", json={"monthly_usd": 10.0, "warn_percent": 80})
    _spend(agent_id, subject, 8.5)
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        check_caller_budgets(session, now)
        check_caller_budgets(session, now)
    mine = [(e, d) for e, d in sent if d["subject"] == subject]
    assert [e for e, _ in mine] == [CALLER_WARNING]
    assert mine[0][1]["percent"] == 85.0

    _spend(agent_id, subject, 2.0)
    with Session(get_engine()) as session:
        check_caller_budgets(session, now)
    assert [e for e, d in sent if d["subject"] == subject] == [CALLER_WARNING, CALLER_EXCEEDED]
