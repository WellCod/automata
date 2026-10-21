"""Webhook de aviso da suíte agendada (ADR-0018): cadastro, saída filtrada e assinatura."""

import hashlib
import hmac
import json
import os
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


class Receiver:
    """Servidor HTTP local que guarda o que recebe e responde com o status configurado."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = self.rfile.read(int(self.headers["Content-Length"]))
                receiver.requests.append({"headers": dict(self.headers), "body": body})
                self.send_response(receiver.status)
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/aviso"


@pytest.fixture(scope="module")
def receiver() -> Generator[Receiver, None, None]:
    r = Receiver()
    yield r
    r.server.shutdown()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "MCP_SECRETS_KEY": Fernet.generate_key().decode(),
            # o receptor local é http em 127.0.0.1: só passa pela allowlist
            "MCP_ALLOWED_HOSTS": "127.0.0.1",
            "DEMO_REPLAY": "true",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _scheduled_agent(client: TestClient, name: str) -> str:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = str(client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"])
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={**body, "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    client.post(
        f"/api/v1/configs/{config_id}/eval-cases",
        json={"name": "responde", "input": "oi", "checks": [{"type": "text", "kind": "not_empty"}]},
    ).raise_for_status()
    client.put(
        f"/api/v1/configs/{config_id}/eval-schedule", json={"cron_expr": "0 8 * * *"}
    ).raise_for_status()
    return config_id


def test_webhook_cadastra_testa_e_assina(client: TestClient, receiver: Receiver) -> None:
    agent = _scheduled_agent(client, "com webhook")
    base = f"/api/v1/configs/{agent}/eval-schedule/webhook"

    saved = client.put(base, json={"url": receiver.url})
    assert saved.status_code == 200, saved.text
    secret = saved.json()["secret"]
    assert saved.json()["host"] == "127.0.0.1"
    schedule = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    # a URL completa não sai da API
    assert schedule["webhook_host"] == "127.0.0.1"
    assert receiver.url not in json.dumps(schedule)

    tested = client.post(f"{base}/test")
    assert tested.json() == {"status": "HTTP 200", "delivered": True}
    sent = receiver.requests[-1]
    payload = json.loads(sent["body"])
    assert payload["event"] == "suite.test"
    assert payload["config_name"] == "com webhook"
    assert payload["text"] == payload["content"] and "com webhook" in payload["text"]
    expected = "sha256=" + hmac.new(secret.encode(), sent["body"], hashlib.sha256).hexdigest()
    assert sent["headers"]["X-Automata-Signature"] == expected
    assert sent["headers"]["X-Automata-Event"] == "suite.test"
    after = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    assert after["webhook_last_status"] == "HTTP 200"

    # trocar a URL gera segredo novo
    again = client.put(base, json={"url": receiver.url}).json()
    assert again["secret"] != secret

    assert client.delete(base).status_code == 204
    gone = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    assert gone["webhook_host"] is None
    assert client.post(f"{base}/test").status_code == 404


def test_receptor_com_erro_fica_registrado(client: TestClient, receiver: Receiver) -> None:
    agent = _scheduled_agent(client, "receptor quebrado")
    base = f"/api/v1/configs/{agent}/eval-schedule/webhook"
    client.put(base, json={"url": receiver.url}).raise_for_status()
    receiver.status = 410
    try:
        tested = client.post(f"{base}/test").json()
    finally:
        receiver.status = 200
    assert tested == {"status": "HTTP 410", "delivered": False}


@pytest.mark.parametrize(
    "url",
    [
        "http://exemplo.com/aviso",  # http fora da allowlist
        "https://localhost/aviso",  # resolve para loopback
        "https://10.0.0.5/aviso",  # rede interna
        "ftp://exemplo.com/aviso",
    ],
)
def test_url_de_saida_proibida_e_recusada(client: TestClient, url: str) -> None:
    agent = _scheduled_agent(client, f"proibido {abs(hash(url))}")
    resp = client.put(f"/api/v1/configs/{agent}/eval-schedule/webhook", json={"url": url})
    assert resp.status_code == 422, resp.text


def test_webhook_sem_agendamento(client: TestClient, receiver: Receiver) -> None:
    body = {"name": "sem agendamento", "description": "x"}
    agent = client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"]
    resp = client.put(f"/api/v1/configs/{agent}/eval-schedule/webhook", json={"url": receiver.url})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Crie o agendamento antes do webhook"


def _tick(agent: str) -> str | None:
    """Um horário vencido: roda a execução agendada e o aviso, como o poller faz."""
    import asyncio
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.evals import scheduler
    from app.evals.notify import notify_after
    from app.evals.runner import execute
    from app.models.eval import EvalSchedule

    with Session(get_engine()) as session:
        session.execute(
            update(EvalSchedule)
            .where(EvalSchedule.agent_config_id == agent)
            .values(next_run_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        session.commit()
    (run_id,) = scheduler.poll_once()
    asyncio.run(execute(run_id))
    return notify_after(run_id)


def _set_check(client: TestClient, agent: str, check: dict[str, Any]) -> None:
    case = client.get(f"/api/v1/configs/{agent}/eval-cases").json()[0]
    client.put(
        f"/api/v1/configs/{agent}/eval-cases/{case['id']}",
        json={"name": case["name"], "input": case["input"], "checks": [check]},
    ).raise_for_status()


def test_avisa_so_nas_mudancas_de_estado(client: TestClient, receiver: Receiver) -> None:
    agent = _scheduled_agent(client, "transicoes")
    client.put(
        f"/api/v1/configs/{agent}/eval-schedule/webhook", json={"url": receiver.url}
    ).raise_for_status()
    sent = len(receiver.requests)

    # primeira agendada verde: nada a avisar
    assert _tick(agent) is None
    # o caso que passava passa a falhar
    _set_check(client, agent, {"type": "text", "kind": "contains", "value": "palavra-ausente"})
    assert _tick(agent) == "suite.regressed"
    regressed = json.loads(receiver.requests[-1]["body"])
    assert regressed["regressions"] == ["responde"]
    assert "regrediu" in regressed["text"] and "transicoes" in regressed["text"]
    # mesmo estado na execução seguinte: silêncio
    assert _tick(agent) is None
    _set_check(client, agent, {"type": "text", "kind": "not_empty"})
    assert _tick(agent) == "suite.recovered"
    assert json.loads(receiver.requests[-1]["body"])["event"] == "suite.recovered"
    assert len(receiver.requests) == sent + 2
    schedule = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    assert schedule["webhook_last_status"] == "HTTP 200"


def test_sem_webhook_nao_avisa(client: TestClient) -> None:
    agent = _scheduled_agent(client, "sem webhook")
    _set_check(client, agent, {"type": "text", "kind": "contains", "value": "palavra-ausente"})
    assert _tick(agent) is None
