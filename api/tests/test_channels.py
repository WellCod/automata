"""Canais de conversa (ADR-0044): cadastro, webhook assinado e resposta do agente."""

import hashlib
import hmac
import json
import os
import time
import uuid
from collections.abc import Generator
from typing import Any

import httpx
import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

REPLY = "Seu pedido sai amanhã."
WA = {
    "access_token": "token-wa",
    "phone_number_id": "1234567890",
    "app_secret": "segredo-do-app",
    "verify_token": "verifica-123",
}
SLACK = {"bot_token": "xoxb-teste", "signing_secret": "segredo-slack"}


class FakeProviders:
    """Graph API e Slack Web API falsos: guardam o que o canal mandou."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.fail_status: int | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.sent.append((str(request.url), body))
        if self.fail_status:
            return httpx.Response(
                self.fail_status, json={"error": {"message": "janela de 24 horas fechada"}}
            )
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"messages": [{"id": f"wamid.{uuid.uuid4().hex}"}]})
        return httpx.Response(200, json={"ok": True, "ts": "1700000000.000200"})


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        os.environ.setdefault("MCP_SECRETS_KEY", Fernet.generate_key().decode())
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeProviders:
    from app.channels import providers

    fake = FakeProviders()
    transport = httpx.MockTransport(fake.handler)
    monkeypatch.setattr(providers, "_http", lambda: httpx.Client(transport=transport))
    return fake


@pytest.fixture
def client(
    db_url: str, fake: FakeProviders, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app

    model = FixedReplyModel(id="claude-haiku-4-5", reply=REPLY, tokens=20)
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _agent(client: TestClient, name: str, publish: bool = True) -> str:
    config_id = str(
        client.post(
            "/api/v1/configs", json={"name": name, "description": f"Use para {name}"}
        ).json()["id"]
    )
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={
            "name": name,
            "description": f"Use para {name}",
            "payload": {"model_id": "claude-haiku-4-5"},
        },
    ).raise_for_status()
    if publish:
        client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _channel(client: TestClient, kind: str, config_id: str, creds: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/channels",
        json={"kind": kind, "name": f"canal {kind}", "config_id": config_id, "credentials": creds},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _wa_body(sender: str, text: str | None, msg_id: str | None = None) -> bytes:
    message: dict[str, Any] = {"from": sender, "id": msg_id or f"wamid.{uuid.uuid4().hex}"}
    if text is None:
        message["type"] = "image"
        message["image"] = {"id": "m1"}
    else:
        message["type"] = "text"
        message["text"] = {"body": text}
    payload = {"entry": [{"changes": [{"value": {"messages": [message]}}]}]}
    return json.dumps(payload).encode()


def _wa_post(client: TestClient, channel: str, body: bytes, secret: str = WA["app_secret"]) -> Any:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        f"/hooks/channels/{channel}",
        content=body,
        headers={"X-Hub-Signature-256": f"sha256={sig}", "Content-Type": "application/json"},
    )


def _slack_post(client: TestClient, channel: str, payload: dict[str, Any], age: int = 0) -> Any:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()) - age)
    sig = hmac.new(
        SLACK["signing_secret"].encode(), b"v0:" + ts.encode() + b":" + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        f"/hooks/channels/{channel}",
        content=body,
        headers={
            "X-Slack-Request-Timestamp": ts,
            "X-Slack-Signature": f"v0={sig}",
            "Content-Type": "application/json",
        },
    )


def _runs(config_id: str) -> list[tuple[str | None, str | None]]:
    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        rows = session.execute(
            select(AgentRun.session_id, AgentRun.user_id).where(
                AgentRun.agent_config_id == uuid.UUID(config_id)
            )
        ).all()
    return [(s, u) for s, u in rows]


def test_cadastro_confere_credencial_e_agente_publicado(client: TestClient) -> None:
    agent = _agent(client, "cadastro")
    draft_only = _agent(client, "só rascunho", publish=False)
    missing = client.post(
        "/api/v1/channels",
        json={
            "kind": "whatsapp",
            "name": "x",
            "config_id": agent,
            "credentials": {"access_token": "t"},
        },
    )
    assert missing.status_code == 422
    assert "phone_number_id" in missing.json()["detail"]
    unpublished = client.post(
        "/api/v1/channels",
        json={"kind": "slack", "name": "x", "config_id": draft_only, "credentials": SLACK},
    )
    assert unpublished.status_code == 422

    channel = _channel(client, "whatsapp", agent, WA)
    listed = client.get("/api/v1/channels").json()
    mine = next(c for c in listed if c["id"] == channel)
    assert mine["webhook_path"] == f"/hooks/channels/{channel}"
    assert mine["credential_fields"] == sorted(WA)
    assert "token-wa" not in json.dumps(listed)

    update = {
        "name": "renomeado",
        "config_id": agent,
        "enabled": True,
        "handoff_enabled": False,
        "handoff_keywords": ["Pessoa"],
        "handoff_message": "Já te passo.",
    }
    resp = client.put(f"/api/v1/channels/{channel}", json=update)
    assert resp.status_code == 200, resp.text
    assert resp.json()["handoff_keywords"] == ["pessoa"]
    assert resp.json()["credential_fields"] == sorted(WA)


def test_verificacao_do_webhook_do_whatsapp(client: TestClient) -> None:
    channel = _channel(client, "whatsapp", _agent(client, "verificação"), WA)
    ok = client.get(
        f"/hooks/channels/{channel}",
        params={"hub.mode": "subscribe", "hub.verify_token": "verifica-123", "hub.challenge": "42"},
    )
    assert ok.status_code == 200 and ok.text == "42"
    wrong = client.get(
        f"/hooks/channels/{channel}",
        params={"hub.mode": "subscribe", "hub.verify_token": "outro", "hub.challenge": "42"},
    )
    assert wrong.status_code == 403
    assert client.get(f"/hooks/channels/{uuid.uuid4()}").status_code == 404


def test_mensagem_do_whatsapp_vira_run_e_resposta(client: TestClient, fake: FakeProviders) -> None:
    agent = _agent(client, "whatsapp")
    channel = _channel(client, "whatsapp", agent, WA)
    body = _wa_body("5511999990000", "Quando chega meu pedido?", "wamid.A1")

    assert _wa_post(client, channel, body, secret="errado").status_code == 401
    assert fake.sent == []
    assert _wa_post(client, channel, body).status_code == 200

    (url, sent) = fake.sent[-1]
    assert url.endswith("/1234567890/messages")
    assert sent["to"] == "5511999990000" and sent["text"]["body"] == REPLY
    ((session_id, user_id),) = _runs(agent)
    assert user_id == "whatsapp:5511999990000"

    # o provedor reenvia a mesma mensagem: o agente não roda de novo
    assert _wa_post(client, channel, body).status_code == 200
    assert len(_runs(agent)) == 1

    # a segunda mensagem da pessoa cai na mesma sessão
    _wa_post(client, channel, _wa_body("5511999990000", "E o rastreio?"))
    assert {s for s, _ in _runs(agent)} == {session_id}


def test_mensagem_que_nao_e_texto_recebe_aviso(client: TestClient, fake: FakeProviders) -> None:
    agent = _agent(client, "não texto")
    channel = _channel(client, "whatsapp", agent, WA)
    _wa_post(client, channel, _wa_body("5511888880000", None))
    assert fake.sent[-1][1]["text"]["body"].startswith("Por enquanto eu só entendo")
    assert _runs(agent) == []


def test_envio_recusado_fica_registrado(client: TestClient, fake: FakeProviders) -> None:
    from app.db import get_engine
    from app.models.channel import ChannelMessage

    agent = _agent(client, "envio recusado")
    channel = _channel(client, "whatsapp", agent, WA)
    fake.fail_status = 400
    _wa_post(client, channel, _wa_body("5511777770000", "oi"))
    with Session(get_engine()) as session:
        out = session.scalars(
            select(ChannelMessage).where(
                ChannelMessage.channel_id == uuid.UUID(channel), ChannelMessage.direction == "out"
            )
        ).one()
    assert out.status == "failed"
    assert out.error and "24 horas" in out.error


def test_slack_responde_na_thread_e_ignora_bot(client: TestClient, fake: FakeProviders) -> None:
    agent = _agent(client, "slack")
    channel = _channel(client, "slack", agent, SLACK)
    challenge = _slack_post(client, channel, {"type": "url_verification", "challenge": "c-1"})
    assert challenge.json() == {"challenge": "c-1"}

    event = {
        "type": "event_callback",
        "event_id": "Ev1",
        "event": {
            "type": "app_mention",
            "user": "U1",
            "text": "<@B1> qual o prazo?",
            "channel": "C1",
            "ts": "1700000000.000100",
        },
    }
    assert _slack_post(client, channel, event).status_code == 200
    (url, sent) = fake.sent[-1]
    assert url.endswith("/chat.postMessage")
    assert sent == {"channel": "C1", "thread_ts": "1700000000.000100", "text": REPLY}
    assert _runs(agent)[0][1] == "slack:U1"

    bot = {**event, "event_id": "Ev2", "event": {**event["event"], "bot_id": "B1"}}
    _slack_post(client, channel, bot)
    assert len(_runs(agent)) == 1
    assert _slack_post(client, channel, {**event, "event_id": "Ev3"}, age=900).status_code == 401


def test_canal_desligado_responde_404(client: TestClient) -> None:
    agent = _agent(client, "desligado")
    channel = _channel(client, "whatsapp", agent, WA)
    client.put(
        f"/api/v1/channels/{channel}",
        json={
            "name": "x",
            "config_id": agent,
            "enabled": False,
            "handoff_enabled": True,
            "handoff_keywords": ["atendente"],
            "handoff_message": "Já te passo.",
        },
    ).raise_for_status()
    assert _wa_post(client, channel, _wa_body("5511666660000", "oi")).status_code == 404
    from app.db import get_engine
    from app.models.channel import ChannelMessage

    with Session(get_engine()) as session:
        count = session.scalar(
            select(func.count(ChannelMessage.id)).where(
                ChannelMessage.channel_id == uuid.UUID(channel)
            )
        )
    assert count == 0
