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
from app.agents.registry import published_config_ids
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
    with PostgresContainer("postgres:17") as pg:
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

    ids = published_config_ids()
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
