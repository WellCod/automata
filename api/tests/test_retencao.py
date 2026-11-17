"""Retenção de conversas por instância (ADR-0045, COM-03).

Antes nada apagava sessões, runs, traces e mensagens de canal: o dado pessoal ficava
para sempre e o banco crescia sem limite.
"""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.settings import get_settings

ANA = "ana@cliente.com"
BIA = "bia@cliente.com"
NOW = datetime.now(UTC)
OLD = NOW - timedelta(days=100)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        patch = pytest.MonkeyPatch()
        patch.setenv("DATABASE_URL", url)
        patch.setenv("JWT_PRIVATE_KEY", "x")
        patch.setenv("JWT_PUBLIC_KEY", "x")
        patch.setenv("DEMO_REPLAY", "true")
        patch.setenv("TRACING_ENABLED", "true")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        import app.agents.factory as factory
        from app.main import create_app

        model = ReplayModel(id="claude-haiku-4-5")
        patch.setattr(factory, "resolve_model", lambda *a, **k: model)
        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        patch.undo()
        get_settings.cache_clear()


def _agent(client: TestClient) -> str:
    agent_id = str(
        client.post("/api/v1/configs", json={"name": "atendimento", "description": "x"}).json()[
            "id"
        ]
    )
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "atendimento",
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5"},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    return agent_id


def _channel_messages(agent_id: str) -> None:
    from app.db import get_engine
    from app.models.channel import Channel, ChannelConversation, ChannelMessage

    with Session(get_engine()) as session:
        channel = Channel(
            kind="whatsapp",
            name="wa",
            config_id=agent_id,
            credentials_encrypted="x",
            created_by="owner",
        )
        session.add(channel)
        session.flush()
        for user, when in ((ANA, OLD), (BIA, NOW)):
            conv = ChannelConversation(
                channel_id=channel.id,
                external_id=user,
                user_id=f"whatsapp:{user}",
                last_message_at=when,
            )
            session.add(conv)
            session.flush()
            session.add(
                ChannelMessage(
                    channel_id=channel.id,
                    conversation_id=conv.id,
                    direction="in",
                    author="customer",
                    text=f"oi, aqui é {user}",
                    status="answered",
                    created_at=when,
                )
            )
        session.commit()


def _backdate(user_id: str) -> None:
    """Põe a conversa de `user_id` 100 dias no passado em todas as tabelas."""
    from app.data_subjects import agno_table_names
    from app.db import get_engine
    from app.models.run import AgentRun
    from app.models.usage import UsageEvent

    names = agno_table_names()
    epoch = int(OLD.timestamp())
    with get_engine().begin() as conn:
        params: dict[str, Any] = {"u": user_id, "e": epoch, "iso": OLD.isoformat()}
        conn.execute(
            text(
                f'update ai."{names["sessions"]}" set created_at=:e, updated_at=:e where user_id=:u'
            ),
            params,
        )
        # sem tracing ligado no processo o Agno não cria a tabela de traces
        if _has(names["traces"]):
            conn.execute(
                text(f'update ai."{names["traces"]}" set created_at=:iso where user_id=:u'), params
            )
        conn.execute(update(AgentRun).where(AgentRun.user_id == user_id).values(created_at=OLD))
        conn.execute(update(UsageEvent).where(UsageEvent.user_id == user_id).values(created_at=OLD))


def _has(name: str) -> bool:
    from sqlalchemy import inspect

    from app.db import get_engine

    return inspect(get_engine()).has_table(name, schema="ai")


def _count(table_key: str, user_id: str) -> int:
    from app.data_subjects import agno_table_names
    from app.db import get_engine

    name = agno_table_names()[table_key]
    if not _has(name):
        return 0
    with get_engine().connect() as conn:
        return int(
            conn.scalar(text(f'select count(*) from ai."{name}" where user_id=:u'), {"u": user_id})
            or 0
        )


def test_retencao_apaga_a_conversa_vencida_e_mantem_metricas(client: TestClient) -> None:
    from app.db import get_engine
    from app.models.channel import ChannelConversation, ChannelMessage
    from app.models.run import AgentRun
    from app.models.usage import UsageEvent
    from app.retention import EXPIRED_USER, purge

    agent_id = _agent(client)
    for user in (ANA, BIA):
        resp = client.post(
            f"/agents/{agent_id}/runs",
            data={"message": f"pedido de {user}", "stream": "false", "user_id": user},
        )
        assert resp.status_code == 200, resp.text
    _channel_messages(agent_id)
    with Session(get_engine()) as session:
        for user in (ANA, BIA):
            session.add(
                UsageEvent(agent_config_id=agent_id, user_id=user, model_id="x", period="202611")
            )
        session.commit()
    _backdate(ANA)
    assert _count("sessions", ANA) == 1

    counts = purge(NOW, 30)

    assert _count("sessions", ANA) == 0
    assert _count("runs", ANA) == 0
    assert _count("traces", ANA) == 0
    # a conversa dentro do prazo fica inteira
    assert _count("sessions", BIA) == 1
    assert _count("runs", BIA) == 1
    with Session(get_engine()) as session:
        runs = session.scalars(select(AgentRun).where(AgentRun.agent_config_id == agent_id)).all()
        users = sorted(r.user_id for r in runs)
        assert users == sorted([BIA, EXPIRED_USER])
        usage = session.scalars(select(UsageEvent.user_id)).all()
        assert ANA not in usage and BIA in usage
        texts = session.scalars(select(ChannelMessage.text)).all()
        assert texts == [f"oi, aqui é {BIA}"]
        conversations = session.scalars(select(ChannelConversation.user_id)).all()
        assert conversations == [f"whatsapp:{BIA}"]
    assert counts["sessions"] == 1 and counts["channel_messages"] == 1

    # rodar de novo não acha mais nada
    assert not any(purge(NOW, 30).values())


def test_retencao_desligada_por_padrao(client: TestClient) -> None:
    import app.retention as retention

    retention._last_run = None
    assert get_settings().conversation_retention_days == 0
    assert retention.purge_daily(NOW) == {}
