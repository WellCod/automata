"""Seção `workflow` do payload: estrutura, regras e validação na escrita (ADR-0014)."""

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.schemas.config import ConfigPayload
from app.schemas.workflow import WorkflowRule, WorkflowSettings
from app.settings import get_settings

A = "00000000-0000-0000-0000-00000000000a"
B = "00000000-0000-0000-0000-00000000000b"


def _step(name: str, agent: str = A) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": agent}


# --- estrutura ---


def test_arvore_com_paralelo_condicao_e_loop() -> None:
    wf = WorkflowSettings.model_validate(
        {
            "steps": [
                _step("triagem"),
                {"type": "parallel", "name": "analises", "branches": [_step("a1"), _step("a2")]},
                {
                    "type": "condition",
                    "name": "se reembolso",
                    "rule": {"kind": "contains", "value": "reembolso"},
                    "steps": [_step("revisao")],
                },
                {
                    "type": "loop",
                    "name": "refino",
                    "steps": [_step("redacao")],
                    "max_iterations": 2,
                },
            ]
        }
    )
    assert [s.type for s in wf.steps] == ["step", "parallel", "condition", "loop"]


@pytest.mark.parametrize(
    ("steps", "trecho"),
    [
        ([_step("x"), _step("x")], "repetidos"),
        (
            [_step("a"), {"type": "parallel", "name": "p", "branches": [_step("b"), _step("c")]}],
            "terminar num paralelo",
        ),
        ([{"type": "step", "name": "sem executor"}], "agente ou de um time"),
        ([{"type": "step", "name": "dois", "agent_id": A, "team_id": B}], "agente ou de um time"),
        (
            [
                {
                    "type": "loop",
                    "name": "l1",
                    "steps": [
                        {
                            "type": "loop",
                            "name": "l2",
                            "steps": [{"type": "loop", "name": "l3", "steps": [_step("fundo")]}],
                        }
                    ],
                }
            ],
            "aninhamento",
        ),
        ([_step(f"e{i}") for i in range(31)], "no máximo 30"),
    ],
)
def test_estrutura_invalida(steps: list[dict[str, Any]], trecho: str) -> None:
    with pytest.raises(ValidationError, match=trecho):
        WorkflowSettings.model_validate({"steps": steps})


def test_regra_de_texto_exige_valor() -> None:
    with pytest.raises(ValidationError, match="precisa de um texto"):
        WorkflowRule(kind="contains", value=" ")
    assert WorkflowRule(kind="empty").value == ""


def test_loop_limita_iteracoes() -> None:
    with pytest.raises(ValidationError):
        WorkflowSettings.model_validate(
            {"steps": [{"type": "loop", "name": "l", "steps": [_step("x")], "max_iterations": 11}]}
        )


def test_payload_sem_modelo_e_valido_no_schema() -> None:
    payload = ConfigPayload.model_validate({"workflow": {"steps": [_step("x")]}})
    assert payload.model_id is None


# --- validação na escrita, com Postgres ---


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=False, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _create(client: TestClient, kind: str, name: str) -> str:
    resp = client.post(
        "/api/v1/configs", json={"name": name, "description": f"Use para {name}", "kind": kind}
    )
    resp.raise_for_status()
    return str(resp.json()["id"])


def _draft(client: TestClient, config_id: str, payload: dict[str, Any]) -> Any:
    return client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": "x", "description": "Use para x", "payload": payload},
    )


def _publish_agent(client: TestClient, name: str, extra: dict[str, Any] | None = None) -> str:
    agent = _create(client, "agent", name)
    _draft(client, agent, {"model_id": "gpt-4o", **(extra or {})}).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()
    return agent


def test_workflow_publica_com_agentes_publicados(client: TestClient) -> None:
    agente = _publish_agent(client, "triagem")
    wf = _create(client, "workflow", "atendimento")
    resp = _draft(client, wf, {"workflow": {"steps": [_step("triagem", agente)]}})
    assert resp.status_code == 201, resp.text
    assert client.post(f"/api/v1/configs/{wf}/publish").status_code == 201
    listed = client.get("/api/v1/configs", params={"kind": "workflow"}).json()["items"]
    assert [c["id"] for c in listed] == [wf]


def test_workflow_recusa_referencias_invalidas(client: TestClient) -> None:
    publicado = _publish_agent(client, "publicado")
    rascunho = _create(client, "agent", "so-rascunho")
    wf = _create(client, "workflow", "invalido")

    def erro(steps: list[dict[str, Any]], **extra: Any) -> str:
        resp = _draft(client, wf, {"workflow": {"steps": steps}, **extra})
        assert resp.status_code == 400, resp.text
        return str(resp.json()["detail"])

    assert "não existe" in erro([_step("x", str(uuid.uuid4()))])
    assert "não tem versão publicada" in erro([_step("x", rascunho)])
    assert "não existe" in erro([{"type": "step", "name": "x", "team_id": publicado}])
    assert "não tem modelo próprio" in erro([_step("x", publicado)], model_id="gpt-4o")
    outra = _publish_agent(client, "outra")
    versao_de_outra = client.get(f"/api/v1/configs/{outra}").json()["current_version"]["id"]
    assert "versão fixada" in erro([{**_step("x", publicado), "version_id": versao_de_outra}])


def test_agente_e_time_continuam_exigindo_modelo(client: TestClient) -> None:
    agente = _create(client, "agent", "sem-modelo")
    resp = _draft(client, agente, {})
    assert resp.status_code == 400
    assert "modelo obrigatório" in resp.text
    assert (
        "só workflow"
        in _draft(client, agente, {"model_id": "gpt-4o", "workflow": {"steps": [_step("x")]}}).text
    )


def test_agente_com_confirmacao_humana_nao_entra(client: TestClient, monkeypatch: Any) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("MCP_SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.interno.local")
    get_settings.cache_clear()
    server = client.post(
        "/api/v1/mcp-servers",
        json={"name": "crm", "slug": "crm", "url": "http://mcp.interno.local/mcp"},
    ).json()
    agente = _publish_agent(
        client,
        "cancelador",
        {
            "mcp_servers": [
                {"server_id": server["id"], "tools": None, "require_confirmation": ["cancelar"]}
            ]
        },
    )
    wf = _create(client, "workflow", "com-confirmacao")
    resp = _draft(client, wf, {"workflow": {"steps": [_step("cancelar", agente)]}})
    assert resp.status_code == 400
    assert "confirmação humana" in resp.text
