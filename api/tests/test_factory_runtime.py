"""Factory e registro contra Postgres real: dono da versão, upsert de run, publicados."""

import os
from collections.abc import Generator

import pytest
from agno.factory.utils import FactoryValidationError
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.factory import load_version
from app.agents.registry import published_configs
from app.agents.tracking import RunRecord, persist
from app.db import get_engine
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.repositories.config import ConfigRepository
from app.schemas.config import CapabilityFlags, ConfigPayload
from app.services.config import ConfigService
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
def publicados(db_url: str) -> Generator[tuple[ConfigService, Session], None, None]:
    with Session(get_engine()) as session:
        yield ConfigService(ConfigRepository(session)), session


def _publica(svc: ConfigService, session: Session, nome: str) -> tuple[object, object]:
    config = svc.create_config(nome, description=f"Use para {nome}")
    svc.save_draft(config.id, ConfigPayload(model_id="gpt-4o"), "autor")
    version = svc.publish(config.id, "autor")
    session.commit()
    return config, version


def test_versao_de_outro_agente_e_recusada(publicados: tuple[ConfigService, Session]) -> None:
    svc, session = publicados
    a, _ = _publica(svc, session, "a")
    _, versao_b = _publica(svc, session, "b")

    with pytest.raises(FactoryValidationError):
        load_version(a.id, versao_b.id)  # type: ignore[attr-defined]


def test_versao_vigente_e_carregada(publicados: tuple[ConfigService, Session]) -> None:
    svc, session = publicados
    config, _ = _publica(svc, session, "vigente")

    resolved = load_version(config.id, None)  # type: ignore[attr-defined]
    assert resolved.payload.model_id == "gpt-4o"
    assert resolved.description == "Use para vigente"


def test_publicados_inclui_so_quem_tem_versao_vigente(
    publicados: tuple[ConfigService, Session],
) -> None:
    svc, session = publicados
    config, _ = _publica(svc, session, "publicado")
    rascunho = svc.create_config("so-rascunho", description="nunca publicado")
    session.commit()

    ids = [i for i, _ in published_configs()]
    assert config.id in ids  # type: ignore[attr-defined]
    assert rascunho.id not in ids


def test_persist_atualiza_run_pausado_e_grava_consumo(
    publicados: tuple[ConfigService, Session],
) -> None:
    svc, session = publicados
    config, _ = _publica(svc, session, "pausa")
    base = {
        "agent_config_id": config.id,  # type: ignore[attr-defined]
        "model_id": "gpt-4o",
        "user_id": "u1",
        "run_id": "run-1",
    }
    persist(RunRecord(**base, status="paused", duration_ms=100))
    persist(RunRecord(**base, status="success", duration_ms=50, total_tokens=30, input_tokens=10))

    runs = session.query(AgentRun).filter_by(run_id="run-1").all()
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].duration_ms == 150
    usage = session.query(UsageEvent).filter_by(run_id="run-1").one()
    assert usage.total_tokens == 30


def test_extended_thinking_liga_thinking_no_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    from agno.models.anthropic import Claude

    from app.agents.models_map import resolve_model

    monkeypatch.delenv("DEMO_REPLAY", raising=False)
    model = resolve_model("claude-sonnet-4-6", CapabilityFlags(extended_thinking=True))
    assert isinstance(model, Claude)
    assert model.thinking is not None
    assert model.thinking["type"] == "enabled"
    sem = resolve_model("claude-sonnet-4-6", CapabilityFlags())
    assert getattr(sem, "thinking", None) is None


def test_publicar_registra_agente_sem_restart_e_run_e_gravado(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.main import create_app

    monkeypatch.setenv("DEMO_REPLAY", "true")
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/configs", json={"name": "ao-vivo", "description": "Use para testes"}
        ).json()
        agent_id = created["id"]
        client.put(
            f"/api/v1/configs/{agent_id}/draft",
            json={
                "name": "ao-vivo",
                "description": "Use para testes",
                "payload": {"model_id": "claude-haiku-4-5"},
            },
        ).raise_for_status()

        assert agent_id not in [a["id"] for a in client.get("/agents").json()]
        client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
        assert agent_id in [a["id"] for a in client.get("/agents").json()]

        run = client.post(f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "false"})
        assert run.status_code == 200, run.text

        runs = client.get(f"/api/v1/configs/{agent_id}/runs").json()
        assert runs["total"] == 1
        assert runs["items"][0]["status"] == "success"
        assert runs["items"][0]["duration_ms"] is not None


# --- agente com tools MCP de verdade ---


@pytest.fixture(scope="module")
def mcp_url() -> Generator[str, None, None]:
    from tests.mcp_fake_server import running_server

    with running_server() as url:
        yield url


@pytest.fixture
def mcp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("MCP_SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "127.0.0.1")
    get_settings.cache_clear()


def _app_with_model(monkeypatch: pytest.MonkeyPatch, model: object) -> object:
    import app.agents.factory as factory

    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    from app.main import create_app

    return create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)


def _agent_with_server(client: object, url: str, slug: str, tools: list[str] | None) -> str:
    from tests.mcp_fake_server import TOKEN

    c = client  # TestClient
    server = c.post(  # type: ignore[attr-defined]
        "/api/v1/mcp-servers",
        json={
            "name": slug,
            "slug": slug,
            "url": url,
            "headers": {"Authorization": f"Bearer {TOKEN}"},
        },
    ).json()
    c.post(f"/api/v1/mcp-servers/{server['id']}/discover").raise_for_status()  # type: ignore[attr-defined]
    agent = c.post(  # type: ignore[attr-defined]
        "/api/v1/configs", json={"name": f"agente-{slug}", "description": "Use para clientes"}
    ).json()
    c.put(  # type: ignore[attr-defined]
        f"/api/v1/configs/{agent['id']}/draft",
        json={
            "name": f"agente-{slug}",
            "description": "Use para clientes",
            "payload": {
                "model_id": "claude-haiku-4-5",
                "mcp_servers": [{"server_id": server["id"], "tools": tools}],
            },
        },
    ).raise_for_status()
    c.post(f"/api/v1/configs/{agent['id']}/publish").raise_for_status()  # type: ignore[attr-defined]
    return str(agent["id"]), str(server["id"])  # type: ignore[return-value]


def test_agente_chama_tool_do_servidor_mcp(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from tests.fake_models import ToolCallingModel, tool_args
    from tests.mcp_fake_server import calls

    model = ToolCallingModel(
        id="claude-haiku-4-5", tool_name="crm_buscar_cliente", tool_args=tool_args(cliente_id="42")
    )
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        agent_id, _ = _agent_with_server(client, mcp_url, "crm", ["buscar_cliente"])
        calls.clear()

        resp = client.post(
            f"/agents/{agent_id}/runs", data={"message": "quem é o 42?", "stream": "false"}
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "COMPLETED"
        assert "Maria" in body["content"]
        assert calls == [("buscar_cliente", {"cliente_id": "42"})]

        runs = client.get(f"/api/v1/configs/{agent_id}/runs").json()
        assert runs["items"][0]["status"] == "success"


def test_tool_fora_da_lista_liberada_nao_chega_ao_agente(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from tests.fake_models import ToolCallingModel, tool_args
    from tests.mcp_fake_server import calls

    model = ToolCallingModel(
        id="claude-haiku-4-5",
        tool_name="crm2_cancelar_assinatura",
        tool_args=tool_args(cliente_id="42"),
    )
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        agent_id, _ = _agent_with_server(client, mcp_url, "crm2", ["buscar_cliente"])
        calls.clear()

        client.post(f"/agents/{agent_id}/runs", data={"message": "cancela o 42", "stream": "false"})
        assert ("cancelar_assinatura", {"cliente_id": "42"}) not in calls


def test_servidor_fora_do_ar_vira_run_com_erro(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from app.models.mcp_server import McpServer

    model = ReplayModelForTest()
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        agent_id, server_id = _agent_with_server(client, mcp_url, "crm3", None)
        with Session(get_engine()) as session:
            row = session.get(McpServer, server_id)
            assert row is not None
            row.url = "http://127.0.0.1:1/mcp"
            session.commit()

        resp = client.post(f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "false"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "ERROR"
        assert "crm3" in resp.json()["content"]

        stream = client.post(f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "true"})
        assert "RunError" in stream.text

        runs = client.get(f"/api/v1/configs/{agent_id}/runs").json()["items"]
        assert [r["status"] for r in runs] == ["error", "error"]
        assert "indisponível" in runs[0]["error"]


def ReplayModelForTest() -> object:  # noqa: N802
    from app.agents.replay import ReplayModel

    return ReplayModel(id="claude-haiku-4-5")


def test_rascunho_recusa_tool_ou_servidor_inexistente(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid

    from fastapi.testclient import TestClient

    with TestClient(_app_with_model(monkeypatch, ReplayModelForTest())) as client:  # type: ignore[arg-type]
        agent_id, server_id = _agent_with_server(client, mcp_url, "crm4", None)

        def draft(bindings: list[dict[str, object]]) -> int:
            return client.put(
                f"/api/v1/configs/{agent_id}/draft",
                json={
                    "name": "x",
                    "description": "Use para clientes",
                    "payload": {"model_id": "claude-haiku-4-5", "mcp_servers": bindings},
                },
            ).status_code

        assert draft([{"server_id": server_id, "tools": ["nao_existe"]}]) == 400
        assert draft([{"server_id": str(uuid.uuid4())}]) == 400
        assert (
            draft(
                [
                    {
                        "server_id": server_id,
                        "tools": ["buscar_cliente"],
                        "require_confirmation": ["cancelar_assinatura"],
                    }
                ]
            )
            == 422
        )
        assert draft([{"server_id": server_id, "tools": ["buscar_cliente"]}]) == 201


def test_payload_v1_gravado_continua_legivel() -> None:
    payload = ConfigPayload.model_validate(
        {"schema_version": 1, "model_id": "gpt-4o", "tools": ["web_search"]}
    )
    assert payload.schema_version == 2
    assert payload.mcp_servers == []


# --- confirmação humana ---


def _agent_with_confirmation(client: object, url: str, slug: str) -> str:
    from tests.mcp_fake_server import TOKEN

    c = client
    server = c.post(  # type: ignore[attr-defined]
        "/api/v1/mcp-servers",
        json={
            "name": slug,
            "slug": slug,
            "url": url,
            "headers": {"Authorization": f"Bearer {TOKEN}"},
        },
    ).json()
    c.post(f"/api/v1/mcp-servers/{server['id']}/discover").raise_for_status()  # type: ignore[attr-defined]
    agent = c.post(  # type: ignore[attr-defined]
        "/api/v1/configs", json={"name": f"agente-{slug}", "description": "Use para cancelar"}
    ).json()
    c.put(  # type: ignore[attr-defined]
        f"/api/v1/configs/{agent['id']}/draft",
        json={
            "name": f"agente-{slug}",
            "description": "Use para cancelar",
            "payload": {
                "model_id": "claude-haiku-4-5",
                "mcp_servers": [
                    {
                        "server_id": server["id"],
                        "tools": ["cancelar_assinatura"],
                        "require_confirmation": ["cancelar_assinatura"],
                    }
                ],
            },
        },
    ).raise_for_status()
    c.post(f"/api/v1/configs/{agent['id']}/publish").raise_for_status()  # type: ignore[attr-defined]
    return str(agent["id"])


@pytest.mark.parametrize("aprovar", [True, False])
def test_tool_sensivel_pausa_e_retoma_com_decisao(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch, aprovar: bool
) -> None:
    import json

    from fastapi.testclient import TestClient

    from tests.fake_models import ToolCallingModel, tool_args
    from tests.mcp_fake_server import calls

    slug = "crmok" if aprovar else "crmnao"
    model = ToolCallingModel(
        id="claude-haiku-4-5",
        tool_name=f"{slug}_cancelar_assinatura",
        tool_args=tool_args(cliente_id="7"),
    )
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        agent_id = _agent_with_confirmation(client, mcp_url, slug)
        calls.clear()

        first = client.post(
            f"/agents/{agent_id}/runs",
            data={"message": "cancela o 7", "stream": "false", "session_id": f"s-{slug}"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "PAUSED"
        assert calls == []

        pending = client.get("/api/v1/approvals", params={"agent_id": agent_id}).json()
        assert len(pending) == 1
        item = pending[0]
        assert item["session_id"] == f"s-{slug}"
        assert item["tools"][0]["tool_name"] == f"{slug}_cancelar_assinatura"
        assert item["tools"][0]["tool_args"] == {"cliente_id": "7"}

        decided = [{**t["tool_execution"], "confirmed": aprovar} for t in item["tools"]]
        resumed = client.post(
            f"/agents/{agent_id}/runs/{item['run_id']}/continue",
            data={
                "tools": json.dumps(decided),
                "session_id": item["session_id"],
                "stream": "false",
            },
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["status"] == "COMPLETED"

        executou = ("cancelar_assinatura", {"cliente_id": "7"}) in calls
        assert executou is aprovar
        assert client.get("/api/v1/approvals", params={"agent_id": agent_id}).json() == []
        runs = client.get(f"/api/v1/configs/{agent_id}/runs").json()["items"]
        assert [r["status"] for r in runs] == ["success"]


# --- times multi-agente ---


def _publish(client: object, kind: str, name: str, payload: dict[str, object]) -> str:
    c = client
    created = c.post(  # type: ignore[attr-defined]
        "/api/v1/configs", json={"name": name, "description": f"Use para {name}", "kind": kind}
    )
    created.raise_for_status()
    config_id = created.json()["id"]
    c.put(  # type: ignore[attr-defined]
        f"/api/v1/configs/{config_id}/draft",
        json={"name": name, "description": f"Use para {name}", "payload": payload},
    ).raise_for_status()
    c.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()  # type: ignore[attr-defined]
    return str(config_id)


def test_time_delega_ao_membro_que_usa_tool_mcp(
    db_url: str, mcp_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from tests.fake_models import DelegatingModel, tool_args
    from tests.mcp_fake_server import TOKEN, calls

    model = DelegatingModel(id="claude-haiku-4-5")
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        server = client.post(
            "/api/v1/mcp-servers",
            json={
                "name": "crmtime",
                "slug": "crmtime",
                "url": mcp_url,
                "headers": {"Authorization": f"Bearer {TOKEN}"},
            },
        ).json()
        client.post(f"/api/v1/mcp-servers/{server['id']}/discover").raise_for_status()
        membro = _publish(
            client,
            "agent",
            "consulta-crm",
            {
                "model_id": "claude-haiku-4-5",
                "mcp_servers": [{"server_id": server["id"], "tools": ["buscar_cliente"]}],
            },
        )
        model.member_id = membro
        model.member_tool = "crmtime_buscar_cliente"
        model.member_tool_args = tool_args(cliente_id="42")

        time = _publish(
            client,
            "team",
            "atendimento",
            {
                "model_id": "claude-haiku-4-5",
                "team": {"mode": "coordinate", "members": [{"agent_id": membro}]},
            },
        )
        assert time in [t["id"] for t in client.get("/teams").json()]
        assert time not in [a["id"] for a in client.get("/agents").json()]

        calls.clear()
        resp = client.post(
            f"/teams/{time}/runs", data={"message": "quem é o 42?", "stream": "false"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "COMPLETED"
        assert calls == [("buscar_cliente", {"cliente_id": "42"})]

        # só o time é registrado; o membro não ganha run próprio
        assert client.get(f"/api/v1/configs/{time}/runs").json()["total"] == 1
        assert client.get(f"/api/v1/configs/{membro}/runs").json()["total"] == 0

        listed = client.get("/api/v1/configs", params={"kind": "team"}).json()["items"]
        assert [c["id"] for c in listed] == [time]
        usam = client.get(f"/api/v1/configs/{membro}/teams").json()
        assert [t["id"] for t in usam] == [time]
        assert client.get(f"/api/v1/configs/{time}/teams").json() == []


def test_time_recusa_membro_invalido(
    db_url: str, mcp_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import uuid

    from fastapi.testclient import TestClient

    with TestClient(_app_with_model(monkeypatch, ReplayModelForTest())) as client:  # type: ignore[arg-type]
        nao_publicado = client.post(
            "/api/v1/configs", json={"name": "rascunho", "description": "x"}
        ).json()["id"]
        time = client.post(
            "/api/v1/configs", json={"name": "t", "description": "x", "kind": "team"}
        ).json()["id"]

        def draft(team: object) -> int:
            return client.put(
                f"/api/v1/configs/{time}/draft",
                json={
                    "name": "t",
                    "description": "x",
                    "payload": {"model_id": "claude-haiku-4-5", "team": team},
                },
            ).status_code

        assert draft(None) == 400
        assert draft({"members": [{"agent_id": str(uuid.uuid4())}]}) == 400
        assert draft({"members": [{"agent_id": nao_publicado}]}) == 400
        assert draft({"members": [{"agent_id": time}]}) == 400
        assert draft({"members": []}) == 422
        assert draft({"mode": "collaborate", "members": [{"agent_id": nao_publicado}]}) == 422

        # agente não aceita seção de time
        resp = client.put(
            f"/api/v1/configs/{nao_publicado}/draft",
            json={
                "name": "rascunho",
                "description": "x",
                "payload": {
                    "model_id": "claude-haiku-4-5",
                    "team": {"members": [{"agent_id": time}]},
                },
            },
        )
        assert resp.status_code == 400


def test_conversa_leva_os_turnos_anteriores_da_sessao(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fastapi.testclient import TestClient

    from tests.fake_models import CountingModel

    model = CountingModel(id="claude-haiku-4-5")
    with TestClient(_app_with_model(monkeypatch, model)) as client:  # type: ignore[arg-type]
        agent = _publish(client, "agent", "memoria", {"model_id": "claude-haiku-4-5"})
        team = _publish(
            client,
            "team",
            "time com memoria",
            {
                "model_id": "claude-haiku-4-5",
                "team": {"mode": "coordinate", "members": [{"agent_id": agent}]},
            },
        )
        for path in (f"/agents/{agent}/runs", f"/teams/{team}/runs"):
            replies = [
                client.post(
                    path, data={"message": msg, "stream": "false", "session_id": f"s-{path}"}
                ).json()["content"]
                for msg in ("oi", "meu pedido é o 123", "qual era o pedido?")
            ]
            assert replies == ["mensagens: 1", "mensagens: 2", "mensagens: 3"], path
            # outra sessão começa do zero
            fresh = client.post(
                path, data={"message": "oi", "stream": "false", "session_id": f"outra-{path}"}
            ).json()["content"]
            assert fresh == "mensagens: 1"
