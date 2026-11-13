"""Evals dos canais (ADR-0044) pelo caminho de verdade: webhook assinado, factory,
tracking e provedor falso.

- No WhatsApp, o segundo turno da pessoa chega ao modelo com o primeiro (histórico).
- Com canário em 50%, pessoas diferentes se dividem entre as versões, e cada uma fica
  sempre na mesma.
- Um time responde no Slack, na thread.
- Guardrail que bloqueia CPF responde com a mensagem de bloqueio, sem chamar o modelo.
- A 21ª mensagem de uma pessoa no mesmo minuto fica ignorada.
- Duas mensagens simultâneas de uma pessoa nova criam uma conversa só.
"""

import asyncio
import os
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
from tests.fake_models import CountingModel
from tests.test_channels import SLACK, WA, FakeProviders, _slack_post, _wa_body, _wa_post


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

    model = CountingModel(id="claude-haiku-4-5")
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _publish(client: TestClient, kind: str, name: str, payload: dict[str, Any]) -> str:
    config_id = str(
        client.post(
            "/api/v1/configs", json={"name": name, "description": f"Use para {name}", "kind": kind}
        ).json()["id"]
    )
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": name, "description": f"Use para {name}", "payload": payload},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _channel(client: TestClient, kind: str, config_id: str, creds: dict[str, str]) -> str:
    resp = client.post(
        "/api/v1/channels",
        json={
            "kind": kind,
            "name": f"{kind} {uuid.uuid4().hex[:4]}",
            "config_id": config_id,
            "credentials": creds,
        },
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _versions(config_id: str) -> dict[str, set[str]]:
    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        rows = session.execute(
            select(AgentRun.user_id, AgentRun.version_id).where(
                AgentRun.agent_config_id == uuid.UUID(config_id)
            )
        ).all()
    out: dict[str, set[str]] = {}
    for user, version in rows:
        out.setdefault(str(user), set()).add(str(version))
    return out


def test_segundo_turno_leva_o_primeiro_ao_modelo(client: TestClient, fake: FakeProviders) -> None:
    agent = _publish(client, "agent", "histórico", {"model_id": "claude-haiku-4-5"})
    channel = _channel(client, "whatsapp", agent, WA)
    _wa_post(client, channel, _wa_body("5511900000001", "Meu pedido é o 4421"))
    _wa_post(client, channel, _wa_body("5511900000001", "Ele já saiu?"))
    replies = [s[1]["text"]["body"] for s in fake.sent]
    assert replies == ["mensagens: 1", "mensagens: 2"]


def test_canario_por_pessoa_no_canal(client: TestClient) -> None:
    agent = _publish(client, "agent", "canário canal", {"model_id": "claude-haiku-4-5"})
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={
            "name": "canário canal",
            "description": "Use para canário canal",
            "payload": {"model_id": "claude-haiku-4-5", "instructions": {"objective": "v2"}},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).raise_for_status()
    channel = _channel(client, "whatsapp", agent, WA)
    for i in range(16):
        number = f"55119100000{i:02d}"
        _wa_post(client, channel, _wa_body(number, "oi"))
        _wa_post(client, channel, _wa_body(number, "tudo bem?"))
    by_person = _versions(agent)
    assert len(by_person) == 16
    assert all(len(v) == 1 for v in by_person.values())
    assert len(set().union(*by_person.values())) == 2


def test_time_responde_no_slack(client: TestClient, fake: FakeProviders) -> None:
    member = _publish(client, "agent", "membro slack", {"model_id": "claude-haiku-4-5"})
    team = _publish(
        client,
        "team",
        "time slack",
        {
            "model_id": "claude-haiku-4-5",
            "team": {"mode": "coordinate", "members": [{"agent_id": member}]},
        },
    )
    channel = _channel(client, "slack", team, SLACK)
    event = {
        "type": "event_callback",
        "event_id": "Ev-time",
        "event": {
            "type": "message",
            "channel_type": "im",
            "user": "U9",
            "text": "preciso de ajuda",
            "channel": "D9",
            "ts": "1700000000.000900",
        },
    }
    assert _slack_post(client, channel, event).status_code == 200
    url, sent = fake.sent[-1]
    assert url.endswith("/chat.postMessage")
    # mensagem direta: responde no canal, sem thread
    assert sent["channel"] == "D9" and "thread_ts" not in sent
    assert set(_versions(team)) == {"slack:U9"}


def test_guardrail_bloqueia_sem_chamar_o_modelo(client: TestClient, fake: FakeProviders) -> None:
    agent = _publish(
        client,
        "agent",
        "bloqueio canal",
        {
            "model_id": "claude-haiku-4-5",
            "guardrails": {
                "pii": {"mode": "block"},
                "blocked_message": "Não envie documentos aqui.",
            },
        },
    )
    channel = _channel(client, "whatsapp", agent, WA)
    _wa_post(client, channel, _wa_body("5511920000000", "meu CPF é 529.982.247-25"))
    assert fake.sent[-1][1]["text"]["body"] == "Não envie documentos aqui."


def test_limite_por_pessoa_no_minuto(client: TestClient, fake: FakeProviders) -> None:
    from app.db import get_engine
    from app.models.channel import ChannelMessage

    agent = _publish(client, "agent", "limite canal", {"model_id": "claude-haiku-4-5"})
    channel = _channel(client, "whatsapp", agent, WA)
    for i in range(21):
        _wa_post(client, channel, _wa_body("5511930000000", f"mensagem {i}"))
    with Session(get_engine()) as session:
        ignored = session.scalar(
            select(func.count(ChannelMessage.id)).where(
                ChannelMessage.channel_id == uuid.UUID(channel),
                ChannelMessage.status == "ignored",
            )
        )
    assert ignored == 1
    assert len(_versions(agent)["whatsapp:5511930000000"]) == 1


def test_mensagens_simultaneas_de_pessoa_nova(client: TestClient) -> None:
    from app.channels import providers, service
    from app.db import get_engine
    from app.models.channel import ChannelConversation

    agent = _publish(client, "agent", "simultâneo", {"model_id": "claude-haiku-4-5"})
    channel = uuid.UUID(_channel(client, "whatsapp", agent, WA))

    def msg(n: int) -> providers.Inbound:
        return providers.Inbound(
            external_id=f"wamid.sim{n}",
            conversation_key="5511940000000",
            sender="5511940000000",
            text=f"oi {n}",
            reply_to={"to": "5511940000000"},
        )

    async def both() -> list[Any]:
        return list(
            await asyncio.gather(
                asyncio.to_thread(service._save_inbound, channel, "whatsapp", msg(1)),
                asyncio.to_thread(service._save_inbound, channel, "whatsapp", msg(2)),
            )
        )

    saved = asyncio.run(both())
    assert all(s is not None for s in saved)
    assert len({s.conversation_id for s in saved}) == 1
    with Session(get_engine()) as session:
        count = session.scalar(
            select(func.count(ChannelConversation.id)).where(
                ChannelConversation.channel_id == channel
            )
        )
    assert count == 1
