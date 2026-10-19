"""Workflows rodando de verdade: sequência, paralelo, condição, loop e erro que para o fluxo."""

import os
from collections.abc import Generator
from typing import Any
from uuid import UUID

import pytest
from agno.models.response import ModelResponse
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.agents.workflow_factory import rule_matches
from app.schemas.workflow import WorkflowRule
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

# cada agente usa um modelo diferente, e o modelo responde um texto fixo
REPLIES = {
    "claude-haiku-4-5": "triagem concluída",
    "claude-sonnet-4-6": "análise técnica ok",
    "gpt-4o-mini": "análise financeira ok",
    "claude-opus-4-7": "consolidado: pronto",
    "o3-mini": "revisão feita",
}


class FailingModel(ReplayModel):
    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise RuntimeError("provedor fora do ar")

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provedor fora do ar")
        yield  # pragma: no cover


def _model(model_id: str, *_: Any, **__: Any) -> ReplayModel:
    if model_id == "gpt-4o":
        return FailingModel(id=model_id)
    return FixedReplyModel(id=model_id, reply=REPLIES[model_id], tokens=10)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        import app.agents.factory as factory

        original = factory.resolve_model
        factory.resolve_model = _model  # type: ignore[assignment]
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        factory.resolve_model = original
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _publish(client: TestClient, kind: str, name: str, payload: dict[str, Any]) -> str:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": kind}).json()["id"]
    client.put(
        f"/api/v1/configs/{config_id}/draft", json={**body, "payload": payload}
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _agent(client: TestClient, name: str, model_id: str) -> str:
    return _publish(client, "agent", name, {"model_id": model_id})


def _step(name: str, agent_id: str, **extra: Any) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": agent_id, **extra}


def _runs(client: TestClient, config_id: str) -> int:
    return int(client.get(f"/api/v1/configs/{config_id}/runs").json()["total"])


def _items(client: TestClient, config_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(f"/api/v1/configs/{config_id}/runs").json()["items"]
    return items


def _parent_ids(config_id: str) -> list[str | None]:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        return list(
            session.scalars(
                select(AgentRun.parent_run_id)
                .where(AgentRun.agent_config_id == UUID(config_id))
                .order_by(AgentRun.created_at)
            )
        )


def _run(client: TestClient, workflow_id: str, message: str) -> dict[str, Any]:
    resp = client.post(
        f"/workflows/{workflow_id}/runs", data={"message": message, "stream": "false"}
    )
    assert resp.status_code == 200, resp.text
    result: dict[str, Any] = resp.json()
    return result


def test_regras() -> None:
    assert rule_matches(WorkflowRule(kind="contains", value="Reembolso"), "quero REEMBOLSO já")
    assert not rule_matches(WorkflowRule(kind="not_contains", value="x"), "tem x")
    assert rule_matches(WorkflowRule(kind="starts_with", value="urgente"), "  Urgente: pagar")
    assert rule_matches(WorkflowRule(kind="empty"), "   ")
    assert rule_matches(WorkflowRule(kind="not_empty"), "a")
    assert rule_matches(WorkflowRule(), "")


def test_sequencia_paralelo_e_condicao(client: TestClient) -> None:
    triagem = _agent(client, "triagem", "claude-haiku-4-5")
    tecnica = _agent(client, "tecnica", "claude-sonnet-4-6")
    financeira = _agent(client, "financeira", "gpt-4o-mini")
    consolida = _agent(client, "consolida", "claude-opus-4-7")
    revisao = _agent(client, "revisao", "o3-mini")
    wf = _publish(
        client,
        "workflow",
        "atendimento",
        {
            "workflow": {
                "steps": [
                    _step("triagem", triagem),
                    {
                        "type": "parallel",
                        "name": "analises",
                        "branches": [_step("tecnica", tecnica), _step("financeira", financeira)],
                    },
                    _step("consolida", consolida),
                    {
                        "type": "condition",
                        "name": "se reembolso",
                        "rule": {"kind": "contains", "source": "input", "value": "reembolso"},
                        "steps": [_step("revisao", revisao)],
                    },
                ]
            }
        },
    )
    assert wf in [w["id"] for w in client.get("/workflows").json()]

    out = _run(client, wf, "quero reembolso do pedido")
    assert out["status"] == "COMPLETED"
    assert out["content"] == "revisão feita"
    for agent in (triagem, tecnica, financeira, consolida, revisao):
        assert _runs(client, agent) == 1
        # ramos paralelos também: a task do gather herda o contexto
        assert _parent_ids(agent) == [out["run_id"]]

    # consumo do workflow é a soma das etapas, sem usage_event próprio
    [run] = _items(client, wf)
    assert run["run_id"] == out["run_id"]
    assert run["steps"] == 5
    assert run["total_tokens"] == 50
    assert _items(client, triagem)[0]["steps"] is None

    out = _run(client, wf, "qual o status do pedido?")
    assert out["status"] == "COMPLETED"
    assert _runs(client, consolida) == 2
    assert _runs(client, revisao) == 1  # condição falsa pulou a revisão


def test_condicao_na_etapa_anterior_e_loop(client: TestClient) -> None:
    triagem = _agent(client, "triagem-2", "claude-haiku-4-5")
    consolida = _agent(client, "consolida-2", "claude-opus-4-7")
    revisao = _agent(client, "revisao-2", "o3-mini")
    wf = _publish(
        client,
        "workflow",
        "com-loop",
        {
            "workflow": {
                "steps": [
                    _step("triagem", triagem),
                    {
                        "type": "condition",
                        "name": "se concluida",
                        "rule": {"kind": "contains", "value": "concluída"},
                        "steps": [_step("revisao", revisao)],
                        "else_steps": [_step("nao-roda", consolida)],
                    },
                    {
                        "type": "loop",
                        "name": "ate pronto",
                        "steps": [_step("consolida", consolida)],
                        "max_iterations": 3,
                        "until": {"kind": "contains", "value": "pronto"},
                    },
                ]
            }
        },
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "COMPLETED"
    assert _runs(client, revisao) == 1
    # loop para na primeira volta (a resposta já diz "pronto") e o else não rodou
    assert _runs(client, consolida) == 1


def test_etapa_com_erro_para_o_fluxo(client: TestClient) -> None:
    quebrado = _agent(client, "quebrado", "gpt-4o")
    depois = _agent(client, "depois", "claude-haiku-4-5")
    wf = _publish(
        client,
        "workflow",
        "para",
        {"workflow": {"steps": [_step("quebrado", quebrado), _step("depois", depois)]}},
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "ERROR"
    assert "fora do ar" in out["content"]
    assert _runs(client, quebrado) == 1
    assert _runs(client, depois) == 0
    runs = client.get(f"/api/v1/configs/{wf}/runs").json()["items"]
    assert [r["status"] for r in runs] == ["error"]

    stream = client.post(f"/workflows/{wf}/runs", data={"message": "oi", "stream": "true"})
    assert "WorkflowError" in stream.text
    assert _runs(client, depois) == 0
    assert _runs(client, wf) == 2
    # no stream o pai também chega à etapa
    parents = _parent_ids(quebrado)
    assert len(parents) == 2 and all(parents)
    assert {r["run_id"] for r in _items(client, wf)} == set(parents)


def test_etapa_marcada_para_seguir(client: TestClient) -> None:
    quebrado = _agent(client, "quebrado-2", "gpt-4o")
    depois = _agent(client, "depois-2", "claude-haiku-4-5")
    wf = _publish(
        client,
        "workflow",
        "segue",
        {
            "workflow": {
                "steps": [
                    _step("quebrado", quebrado, on_error="continue"),
                    _step("depois", depois),
                ]
            }
        },
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "COMPLETED"
    assert _runs(client, depois) == 1
