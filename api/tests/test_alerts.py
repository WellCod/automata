"""Destinos de aviso da instância (ADR-0021): cadastro, orçamento e pico de erro."""

import hashlib
import hmac
import json
import os
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel
from tests.test_eval_webhook import Receiver

ALL_EVENTS = [
    "budget.warning",
    "budget.exceeded",
    "errors.spike",
    "suite.regressed",
    "suite.failing",
    "suite.recovered",
]


@pytest.fixture(scope="module")
def receiver() -> Generator[Receiver, None, None]:
    r = Receiver()
    yield r
    r.server.shutdown()


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "MCP_SECRETS_KEY": Fernet.generate_key().decode(),
            # o receptor local é http em 127.0.0.1: só passa pela allowlist
            "MCP_ALLOWED_HOSTS": "127.0.0.1",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app

    # US$ 0,005 por run: 1.000 tokens de saída do haiku pela tabela de preços
    model = FixedReplyModel(id="claude-haiku-4-5", reply="ok", tokens=1_000)
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _agent(client: TestClient, name: str) -> str:
    body = {"name": name, "description": "x"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"]
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={**body, "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _events(receiver: Receiver, since: int) -> list[str]:
    return [json.loads(r["body"])["event"] for r in receiver.requests[since:]]


def test_destino_cadastra_testa_assina_e_nao_expoe_a_url(
    client: TestClient, receiver: Receiver
) -> None:
    created = client.post(
        "/api/v1/alert-destinations",
        json={"name": "canal do time", "url": receiver.url, "events": ["errors.spike"]},
    )
    assert created.status_code == 201, created.text
    dest = created.json()
    assert dest["host"] == "127.0.0.1"
    listed = client.get("/api/v1/alert-destinations").json()
    assert receiver.url not in json.dumps(listed)
    assert "secret" not in listed[0]

    tested = client.post(f"/api/v1/alert-destinations/{dest['id']}/test").json()
    assert tested == {"status": "HTTP 200", "delivered": True}
    sent = receiver.requests[-1]
    expected = hmac.new(dest["secret"].encode(), sent["body"], hashlib.sha256).hexdigest()
    assert sent["headers"]["X-Automata-Signature"] == "sha256=" + expected
    assert json.loads(sent["body"])["event"] == "alert.test"

    updated = client.put(
        f"/api/v1/alert-destinations/{dest['id']}",
        json={"name": "canal novo", "events": ["budget.warning", "budget.warning"]},
    ).json()
    assert updated["events"] == ["budget.warning"]
    assert updated["last_status"] == "HTTP 200"
    assert client.delete(f"/api/v1/alert-destinations/{dest['id']}").status_code == 204
    assert client.get("/api/v1/alert-destinations").json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "url": "https://10.0.0.5/aviso", "events": ["errors.spike"]},
        {"name": "x", "url": "https://exemplo.com/aviso", "events": []},
        {"name": "x", "url": "https://exemplo.com/aviso", "events": ["evento.inventado"]},
    ],
)
def test_destino_invalido_e_recusado(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/api/v1/alert-destinations", json=body).status_code == 422


def test_orcamento_avisa_uma_vez_por_nivel_no_mes(client: TestClient, receiver: Receiver) -> None:
    from app import alerts

    dest = client.post(
        "/api/v1/alert-destinations",
        json={"name": "orçamento", "url": receiver.url, "events": ALL_EVENTS},
    ).json()
    agent = _agent(client, "gasta")
    client.put(
        f"/api/v1/configs/{agent}/budget",
        json={"monthly_usd": 0.01, "alert_percent": 50, "hard_stop": False},
    ).raise_for_status()
    start = len(receiver.requests)

    client.post(f"/agents/{agent}/runs", data={"message": "oi", "stream": "false"})
    alerts.poll_once()
    alerts.poll_once()
    assert _events(receiver, start) == ["budget.warning"]
    warning = json.loads(receiver.requests[-1]["body"])
    assert warning["config_name"] == "gasta" and warning["percent"] == 50
    assert "50%" in warning["text"] and "US$ 0,01" in warning["text"]

    client.post(f"/agents/{agent}/runs", data={"message": "oi", "stream": "false"})
    alerts.poll_once()
    alerts.poll_once()
    assert _events(receiver, start) == ["budget.warning", "budget.exceeded"]
    assert "estourou" in json.loads(receiver.requests[-1]["body"])["text"]
    client.delete(f"/api/v1/alert-destinations/{dest['id']}").raise_for_status()


def test_pico_de_erro_avisa_uma_vez_por_hora(client: TestClient, receiver: Receiver) -> None:
    from sqlalchemy.orm import Session

    from app import alerts
    from app.db import get_engine
    from app.models.run import AgentRun

    dest = client.post(
        "/api/v1/alert-destinations",
        json={"name": "erros", "url": receiver.url, "events": ["errors.spike"]},
    ).json()
    quebrado = _agent(client, "quebrado")
    pouco = _agent(client, "pouco movimento")
    with Session(get_engine()) as session:
        # 3 erros em 5 runs: 60%
        for status in ("error", "error", "error", "success", "success"):
            session.add(AgentRun(agent_config_id=quebrado, user_id="u", status=status))
        # bloqueio não é erro
        for _ in range(5):
            session.add(AgentRun(agent_config_id=quebrado, user_id="u", status="blocked"))
        # 4 erros em 4 runs: abaixo do mínimo de 5
        for _ in range(4):
            session.add(AgentRun(agent_config_id=pouco, user_id="u", status="error"))
        session.commit()
    start = len(receiver.requests)

    alerts.poll_once()
    alerts.poll_once(datetime.now(UTC))
    assert _events(receiver, start) == ["errors.spike"]
    spike = json.loads(receiver.requests[-1]["body"])
    assert spike["config_name"] == "quebrado"
    assert (spike["runs"], spike["errors"]) == (5, 3)
    assert "60%" in spike["text"]
    client.delete(f"/api/v1/alert-destinations/{dest['id']}").raise_for_status()


def test_sem_destino_nada_e_reservado(client: TestClient) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app import alerts
    from app.db import get_engine
    from app.models.alert import AlertSent

    agent = _agent(client, "sem destino")
    client.put(f"/api/v1/configs/{agent}/budget", json={"monthly_usd": 0.001}).raise_for_status()
    client.post(f"/agents/{agent}/runs", data={"message": "oi", "stream": "false"})
    alerts.poll_once()
    with Session(get_engine()) as session:
        count = session.scalar(
            select(func.count()).select_from(AlertSent).where(AlertSent.agent_config_id == agent)
        )
    # sem reserva, um destino cadastrado depois ainda recebe o aviso do mês
    assert count == 0
