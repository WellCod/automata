"""Agente com base de conhecimento: validação, tool, instruções, run e remoção (ADR-0012)."""

import json
import os
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.linter.prompt import lint_payload
from app.schemas.config import ConfigPayload, KnowledgeBinding
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


def _app(monkeypatch: pytest.MonkeyPatch, model: object | None = None) -> Any:
    import app.agents.factory as factory

    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    if model is not None:
        monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    from app.main import create_app

    return create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)


def _base_com_documento(client: TestClient, slug: str) -> str:
    base = client.post(
        "/api/v1/knowledge-bases",
        json={"name": f"Base {slug}", "slug": slug, "description": "Políticas de RH"},
    ).json()
    client.post(
        f"/api/v1/knowledge-bases/{base['id']}/contents/text",
        json={"name": "Férias", "text": "Cada colaborador tem trinta dias de férias por ano."},
    ).raise_for_status()
    return str(base["id"])


def _agente(client: TestClient, nome: str, payload: dict[str, Any]) -> tuple[str, Any]:
    agent = client.post("/api/v1/configs", json={"name": nome, "description": "Use para RH"})
    agent_id = agent.json()["id"]
    resp = client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={"name": nome, "description": "Use para RH", "payload": payload},
    )
    return agent_id, resp


def test_base_inexistente_ou_repetida_e_recusada(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(_app(monkeypatch)) as client:
        _, resp = _agente(
            client,
            "sem-base",
            {
                "model_id": "claude-haiku-4-5",
                "knowledge": [{"base_id": "00000000-0000-0000-0000-000000000001"}],
            },
        )
        # erro do serviço segue a convenção dos servidores MCP: 400
        assert resp.status_code == 400
        assert "não existe" in resp.text

        base_id = _base_com_documento(client, "repetida")
        _, resp = _agente(
            client,
            "repetida",
            {
                "model_id": "claude-haiku-4-5",
                "knowledge": [{"base_id": base_id}, {"base_id": base_id}],
            },
        )
        assert resp.status_code == 422


def test_agente_busca_na_base_e_ve_a_fonte(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.fake_models import ToolCallingModel, tool_args

    model = ToolCallingModel(
        id="claude-haiku-4-5", tool_name="buscar_rh", tool_args=tool_args(pergunta="férias")
    )
    with TestClient(_app(monkeypatch, model)) as client:
        base_id = _base_com_documento(client, "rh")
        agent_id, resp = _agente(
            client,
            "assistente-rh",
            {"model_id": "claude-haiku-4-5", "knowledge": [{"base_id": base_id, "max_results": 2}]},
        )
        assert resp.status_code in (200, 201), resp.text
        client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()

        run = client.post(
            f"/agents/{agent_id}/runs",
            data={"message": "quantos dias de férias?", "stream": "false"},
        )
        assert run.status_code == 200, run.text
        body = run.json()
        assert body["status"] == "COMPLETED"
        result = json.loads(body["content"].removeprefix("resultado: "))
        assert result["base"] == "Base rh"
        assert result["trechos"][0]["documento"] == "Férias"
        assert "trinta dias" in result["trechos"][0]["texto"]


def test_factory_monta_tool_e_instrucao(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from uuid import UUID

    from app.agents.factory import agent_from, load_version

    with TestClient(_app(monkeypatch)) as client:
        base_id = _base_com_documento(client, "manual")
        agent_id, _ = _agente(
            client,
            "com-manual",
            {
                "model_id": "claude-haiku-4-5",
                "knowledge": [{"base_id": base_id}],
                "instructions": {"guardrails": "Só responda sobre RH."},
            },
        )
        client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()

        resolved = load_version(UUID(agent_id), None)
        agent = agent_from(UUID(agent_id), resolved, tracked=False)
        names = [getattr(t, "name", None) for t in agent.tools or []]
        assert names == ["buscar_manual"]
        assert isinstance(agent.instructions, str)
        assert "buscar_manual: Base manual — Políticas de RH" in agent.instructions
        assert "não instrução" in agent.instructions
        assert agent.instructions.startswith("Só responda sobre RH.")


def test_base_em_uso_nao_pode_ser_removida(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    with TestClient(_app(monkeypatch)) as client:
        base_id = _base_com_documento(client, "em_uso")
        _agente(
            client,
            "usa-base",
            {"model_id": "claude-haiku-4-5", "knowledge": [{"base_id": base_id}]},
        )

        resp = client.delete(f"/api/v1/knowledge-bases/{base_id}")
        assert resp.status_code == 409
        assert "usa-base" in resp.text


def test_linter_avisa_base_sem_guardrail() -> None:
    from uuid import uuid4

    sem = ConfigPayload(model_id="gpt-4o", knowledge=[KnowledgeBinding(base_id=uuid4())])
    codes = [w.code for w in lint_payload(sem)]
    assert "knowledge-without-guardrail" in codes

    com = sem.model_copy(deep=True)
    com.instructions.guardrails = "Se a base não cobrir, diga que não sabe."
    assert "knowledge-without-guardrail" not in [w.code for w in lint_payload(com)]
