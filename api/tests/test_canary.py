"""Liberação gradual de versão (ADR-0040): sorteio pela sessão, versão no run e rotas."""

import os
import uuid
from collections.abc import Generator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.canary import bucket, in_canary
from app.settings import get_settings
from tests.fake_models import FixedReplyModel


def test_balde_estavel_para_a_mesma_conversa() -> None:
    config = uuid.uuid4()
    assert bucket(config, "s1") == bucket(config, "s1")
    assert 0 <= bucket(config, "s1") < 100


def test_percentual_aproximado_e_teto_de_50() -> None:
    config = uuid.uuid4()
    hits = sum(in_canary(config, f"s{i}", 20) for i in range(5_000))
    assert 850 < hits < 1_150
    over = sum(in_canary(config, f"s{i}", 90) for i in range(5_000))
    assert over < 2_700
    assert not in_canary(config, "s1", None)
    assert not in_canary(config, "s1", 0)


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


def _draft(client: TestClient, config_id: str, instructions: str) -> None:
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={
            "name": "x",
            "description": "x",
            "payload": {
                "model_id": "claude-haiku-4-5",
                "instructions": {"objective": instructions},
            },
        },
    ).raise_for_status()


def _agent(client: TestClient, name: str) -> str:
    config_id = str(
        client.post(
            "/api/v1/configs", json={"name": name, "description": "x", "kind": "agent"}
        ).json()["id"]
    )
    _draft(client, config_id, "v1")
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _current(client: TestClient, config_id: str) -> str:
    return str(client.get(f"/api/v1/configs/{config_id}").json()["current_version"]["id"])


def _run(client: TestClient, agent: str, session_id: str) -> None:
    resp = client.post(
        f"/agents/{agent}/runs",
        data={"message": "oi", "stream": "false", "session_id": session_id},
    )
    resp.raise_for_status()


def _run_versions(agent: str) -> dict[str, set[str]]:
    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        rows = session.execute(
            select(AgentRun.session_id, AgentRun.version_id).where(
                AgentRun.agent_config_id == uuid.UUID(agent)
            )
        ).all()
    out: dict[str, set[str]] = {}
    for sid, vid in rows:
        out.setdefault(str(sid), set()).add(str(vid))
    return out


def test_canario_do_rascunho_divide_as_conversas_e_grava_a_versao(client: TestClient) -> None:
    agent = _agent(client, "canário rascunho")
    current = _current(client, agent)
    _draft(client, agent, "v2")

    started = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50})
    assert started.status_code == 201, started.text
    state = started.json()
    assert state["active"] is True
    canary = state["canary"]["version_id"]
    assert canary != current
    # a vigente não mudou e o rascunho virou versão publicada
    assert _current(client, agent) == current

    for i in range(12):
        _run(client, agent, f"conversa-{i}")
    _run(client, agent, "conversa-0")

    seen = _run_versions(agent)
    # a mesma conversa fica numa versão só
    assert all(len(v) == 1 for v in seen.values())
    used = set().union(*seen.values())
    assert used == {current, canary}

    stats = client.get(f"/api/v1/configs/{agent}/canary").json()
    assert stats["current"]["runs"] + stats["canary"]["runs"] == 13
    assert stats["canary"]["error_rate"] == 0
    assert stats["canary"]["p50_ms"] is not None


def test_regras_de_inicio_e_percentual(client: TestClient) -> None:
    agent = _agent(client, "canário regras")
    current = _current(client, agent)

    # sem rascunho
    assert client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10}).status_code == 400
    # a vigente não serve de canário
    same = client.post(
        f"/api/v1/configs/{agent}/canary", json={"percent": 10, "version_id": current}
    )
    assert same.status_code == 422
    assert client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 51}).status_code == 422
    # PATCH sem canário
    assert client.patch(f"/api/v1/configs/{agent}/canary", json={"percent": 5}).status_code == 409

    _draft(client, agent, "v2")
    assert client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10}).status_code == 201
    assert client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10}).status_code == 409
    patched = client.patch(f"/api/v1/configs/{agent}/canary", json={"percent": 30})
    assert patched.json()["percent"] == 30


def test_versao_publicada_antiga_como_canario_e_promocao(client: TestClient) -> None:
    agent = _agent(client, "canário promoção")
    v1 = _current(client, agent)
    _draft(client, agent, "v2")
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()
    v2 = _current(client, agent)

    started = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 20, "version_id": v1})
    assert started.status_code == 201, started.text

    promoted = client.post(f"/api/v1/configs/{agent}/canary/promote")
    assert promoted.status_code == 200
    assert promoted.json()["active"] is False
    assert _current(client, agent) == v1 != v2


def test_publicar_rollback_e_desligar_encerram_o_canario(client: TestClient) -> None:
    agent = _agent(client, "canário encerra")
    v1 = _current(client, agent)
    _draft(client, agent, "v2")
    first = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10})
    v2 = first.json()["canary"]["version_id"]

    _draft(client, agent, "v3")
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()
    assert client.get(f"/api/v1/configs/{agent}/canary").json()["active"] is False

    client.post(
        f"/api/v1/configs/{agent}/canary", json={"percent": 10, "version_id": v1}
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/rollback", json={"version_id": v2}).raise_for_status()
    assert client.get(f"/api/v1/configs/{agent}/canary").json()["active"] is False

    client.post(
        f"/api/v1/configs/{agent}/canary", json={"percent": 10, "version_id": v1}
    ).raise_for_status()
    stopped = client.delete(f"/api/v1/configs/{agent}/canary")
    assert stopped.status_code == 200
    assert stopped.json()["active"] is False
    # sem canário ligado não há o que desligar, nem linha vazia na trilha
    assert client.delete(f"/api/v1/configs/{agent}/canary").status_code == 409


def test_versao_pedida_vence_o_canario(client: TestClient) -> None:
    from app.agents.factory import load_version

    agent = _agent(client, "canário teste")
    v1 = _current(client, agent)
    _draft(client, agent, "v2")
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).raise_for_status()

    for i in range(20):
        resolved = load_version(uuid.UUID(agent), uuid.UUID(v1), f"s{i}")
        assert str(resolved.version_id) == v1


def test_conversa_sem_sessao_fica_na_versao_do_primeiro_turno(client: TestClient) -> None:
    from app.agents.canary import in_canary

    agent = _agent(client, "canário sem sessão")
    current = _current(client, agent)
    _draft(client, agent, "v2")
    canary = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).json()
    canary_id = canary["canary"]["version_id"]

    for _ in range(16):
        resp = client.post(f"/agents/{agent}/runs", data={"message": "oi", "stream": "false"})
        resp.raise_for_status()
        session = resp.json()["session_id"]
        # o primeiro turno já caiu na versão da sessão que o middleware gerou
        expected = canary_id if in_canary(uuid.UUID(agent), session, 50) else current
        _run(client, agent, session)
        assert _run_versions(agent)[session] == {expected}


def test_membro_etapa_e_suite_ficam_na_vigente(client: TestClient) -> None:
    from app.agents.factory import load_team, load_version

    agent = _agent(client, "canário membro")
    current = _current(client, agent)
    _draft(client, agent, "v2")
    client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 50}).raise_for_status()
    for i in range(20):
        # sem `canary=True` (membro, etapa, suíte), nunca sorteia
        assert str(load_version(uuid.UUID(agent), None, f"s{i}").version_id) == current
        assert str(load_version(uuid.UUID(agent), None).version_id) == current

    team = client.post(
        "/api/v1/configs", json={"name": "time canário", "description": "x", "kind": "team"}
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{team}/draft",
        json={
            "name": "t",
            "description": "x",
            "payload": {
                "model_id": "claude-haiku-4-5",
                "team": {"mode": "coordinate", "members": [{"agent_id": agent}]},
            },
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{team}/publish").raise_for_status()
    for i in range(20):
        resolved = load_team(uuid.UUID(team), None, f"s{i}", canary=True)
        ((_, member),) = resolved.members
        assert str(member.version_id) == current


def test_comparacao_ignora_run_filho(client: TestClient) -> None:
    from app.agents.tracking import RunRecord, persist

    agent = _agent(client, "canário filho")
    _draft(client, agent, "v2")
    canary = client.post(f"/api/v1/configs/{agent}/canary", json={"percent": 10}).json()
    persist(
        RunRecord(
            agent_config_id=uuid.UUID(agent),
            model_id="claude-haiku-4-5",
            user_id="u",
            run_id=f"{agent}-filho",
            status="success",
            duration_ms=10,
            parent_run_id="workflow-run",
            version_id=uuid.UUID(canary["canary"]["version_id"]),
        )
    )
    assert client.get(f"/api/v1/configs/{agent}/canary").json()["canary"]["runs"] == 0
