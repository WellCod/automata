"""Evals da liberação gradual (ADR-0040) pela rota do AgentOS, pela factory e pelo tracking.

- 120 conversas com canário em 25% caem perto de 25% na versão nova, cada uma numa versão só.
- O líder do time segue o canário e o run do time grava a versão dele.
- O modo teste, com `factory_input.version_id`, nunca cai no canário.
- Publicar no meio do canário volta tudo para a vigente nova.
- A comparação conta só a conversa da versão desde o início do canário.
"""

import json
import os
import uuid
from collections import Counter
from collections.abc import Generator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel


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

    model = FixedReplyModel(id="claude-haiku-4-5", reply="ok", tokens=100)
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _save(client: TestClient, config_id: str, payload: dict[str, object]) -> None:
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": "x", "description": "x", "payload": payload},
    ).raise_for_status()


def _create(client: TestClient, kind: str, name: str, payload: dict[str, object]) -> str:
    config_id = str(
        client.post(
            "/api/v1/configs", json={"name": name, "description": "x", "kind": kind}
        ).json()["id"]
    )
    _save(client, config_id, payload)
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _current(client: TestClient, config_id: str) -> str:
    return str(client.get(f"/api/v1/configs/{config_id}").json()["current_version"]["id"])


def _agent_payload(objective: str) -> dict[str, object]:
    return {"model_id": "claude-haiku-4-5", "instructions": {"objective": objective}}


def _versions_by_session(config_id: str) -> dict[str, set[str]]:
    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        rows = session.execute(
            select(AgentRun.session_id, AgentRun.version_id).where(
                AgentRun.agent_config_id == uuid.UUID(config_id)
            )
        ).all()
    out: dict[str, set[str]] = {}
    for sid, vid in rows:
        out.setdefault(str(sid), set()).add(str(vid))
    return out


def test_distribuicao_por_sessao_pela_rota(client: TestClient) -> None:
    agent = _create(client, "agent", "distribuição", _agent_payload("v1"))
    current = _current(client, agent)
    _save(client, agent, _agent_payload("v2"))
    canary = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 25}).json()
    canary_id = canary["canary"]["version_id"]

    for i in range(120):
        client.post(
            f"/agents/{agent}/runs",
            data={"message": "oi", "stream": "false", "session_id": f"cliente-{i}"},
        ).raise_for_status()
    # segunda mensagem das 20 primeiras conversas
    for i in range(20):
        client.post(
            f"/agents/{agent}/runs",
            data={"message": "e agora?", "stream": "false", "session_id": f"cliente-{i}"},
        ).raise_for_status()

    seen = _versions_by_session(agent)
    assert len(seen) == 120
    assert all(len(v) == 1 for v in seen.values())
    counts = Counter(next(iter(v)) for v in seen.values())
    assert set(counts) == {current, canary_id}
    assert 15 <= counts[canary_id] <= 45

    stats = client.get(f"/api/v1/configs/{agent}/canary").json()
    assert stats["current"]["runs"] + stats["canary"]["runs"] == 140


def test_lider_do_time_segue_o_canario(client: TestClient) -> None:
    member = _create(client, "agent", "membro", _agent_payload("membro"))
    team_payload: dict[str, object] = {
        "model_id": "claude-haiku-4-5",
        "team": {"mode": "coordinate", "members": [{"agent_id": member}]},
    }
    team = _create(client, "team", "time canário", team_payload)
    current = _current(client, team)
    _save(client, team, {**team_payload, "instructions": {"objective": "v2"}})
    started = client.post(f"/api/v1/configs/{team}/canary", json={"percent": 50})
    assert started.status_code == 201, started.text
    canary_id = started.json()["canary"]["version_id"]

    for i in range(30):
        client.post(
            f"/teams/{team}/runs",
            data={"message": "oi", "stream": "false", "session_id": f"t-{i}"},
        ).raise_for_status()

    used = set().union(*_versions_by_session(team).values())
    assert used == {current, canary_id}
    # o membro não tem canário nem run próprio
    assert client.get(f"/api/v1/configs/{member}/canary").json()["active"] is False


def test_modo_teste_usa_a_versao_pedida(client: TestClient) -> None:
    agent = _create(client, "agent", "modo teste", _agent_payload("v1"))
    current = _current(client, agent)
    _save(client, agent, _agent_payload("v2"))
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).raise_for_status()

    for i in range(20):
        client.post(
            f"/agents/{agent}/runs",
            data={
                "message": "oi",
                "stream": "false",
                "session_id": f"teste-{i}",
                "factory_input": json.dumps({"version_id": current}),
            },
        ).raise_for_status()

    used = set().union(*_versions_by_session(agent).values())
    assert used == {current}


def test_publicar_no_meio_do_canario_volta_tudo_para_a_vigente(client: TestClient) -> None:
    agent = _create(client, "agent", "publica no meio", _agent_payload("v1"))
    _save(client, agent, _agent_payload("v2"))
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).raise_for_status()
    _save(client, agent, _agent_payload("v3"))
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()
    newest = _current(client, agent)

    for i in range(20):
        client.post(
            f"/agents/{agent}/runs",
            data={"message": "oi", "stream": "false", "session_id": f"p-{i}"},
        ).raise_for_status()

    assert set().union(*_versions_by_session(agent).values()) == {newest}
    assert client.get(f"/api/v1/configs/{agent}/canary").json()["active"] is False


def test_comparacao_ignora_runs_de_antes_do_canario(client: TestClient) -> None:
    from datetime import UTC, datetime, timedelta

    from app.agents.tracking import RunRecord, persist
    from app.db import get_engine
    from app.models.run import AgentRun

    agent = _create(client, "agent", "comparação", _agent_payload("v1"))
    current = uuid.UUID(_current(client, agent))
    _save(client, agent, _agent_payload("v2"))
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10}).raise_for_status()

    for run_id, status in (("antigo", "success"), ("novo", "error")):
        persist(
            RunRecord(
                agent_config_id=uuid.UUID(agent),
                model_id="claude-haiku-4-5",
                user_id="u",
                run_id=f"{agent}-{run_id}",
                status=status,
                duration_ms=100,
                version_id=current,
            )
        )
    with Session(get_engine()) as session:
        old = session.scalars(select(AgentRun).where(AgentRun.run_id == f"{agent}-antigo")).one()
        old.created_at = datetime.now(UTC) - timedelta(days=1)
        session.commit()

    stats = client.get(f"/api/v1/configs/{agent}/canary").json()
    assert stats["current"]["runs"] == 1
    assert stats["current"]["error_rate"] == 1
    assert stats["canary"]["runs"] == 0
