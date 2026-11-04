"""Roteador por regras e entrada por etapa no workflow (ADR-0038), rodando de verdade."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from agno.models.response import ModelResponse
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.settings import get_settings
from tests.fake_models import FixedReplyModel


class EchoModel(ReplayModel):
    """Responde com a última mensagem do usuário: mostra o que a etapa recebeu."""

    def _respond(self, messages: Any) -> ModelResponse:
        users = [m for m in messages or [] if getattr(m, "role", None) == "user"]
        text = str(users[-1].content) if users else ""
        return ModelResponse(role="assistant", content=f"recebi: {text}")

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(kwargs.get("messages"))


REPLIES = {"claude-haiku-4-5": "triagem: troca", "claude-opus-4-7": "caminho do padrão"}


def _model(model_id: str, *_: Any, **__: Any) -> ReplayModel:
    if model_id == "claude-sonnet-4-6":
        return EchoModel(id=model_id)
    return FixedReplyModel(id=model_id, reply=REPLIES[model_id], tokens=5)


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        os.environ["DATABASE_URL"] = pg.get_connection_url().replace("psycopg2", "psycopg")
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


def _publish(client: TestClient, kind: str, name: str, payload: dict[str, Any]) -> Any:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": kind}).json()["id"]
    draft = client.put(f"/api/v1/configs/{config_id}/draft", json={**body, "payload": payload})
    if draft.status_code >= 400:
        return draft
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _agent(client: TestClient, name: str, model_id: str) -> str:
    agent = _publish(client, "agent", name, {"model_id": model_id})
    assert isinstance(agent, str)
    return agent


def _step(name: str, agent_id: str, **extra: Any) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": agent_id, **extra}


def _run(client: TestClient, workflow_id: str, message: str) -> dict[str, Any]:
    resp = client.post(
        f"/workflows/{workflow_id}/runs", data={"message": message, "stream": "false"}
    )
    assert resp.status_code == 200, resp.text
    result: dict[str, Any] = resp.json()
    return result


def _router(eco: str, padrao: str) -> dict[str, Any]:
    return {
        "type": "router",
        "name": "destino",
        "routes": [
            {
                "rule": {"kind": "contains", "value": "troca", "source": "input"},
                "step": _step("troca", eco),
            },
            {
                "rule": {"kind": "contains", "value": "reembolso", "source": "input"},
                "step": _step("reembolso", eco, input="template", template="REEMBOLSO {entrada}"),
            },
        ],
        "default": _step("padrao", padrao),
    }


def test_roteador_escolhe_o_caminho_ou_o_padrao(client: TestClient) -> None:
    eco = _agent(client, "eco", "claude-sonnet-4-6")
    padrao = _agent(client, "padrao", "claude-opus-4-7")
    wf = _publish(
        client, "workflow", "atendimento", {"workflow": {"steps": [_router(eco, padrao)]}}
    )
    assert _run(client, wf, "quero fazer uma troca")["content"] == "recebi: quero fazer uma troca"
    assert _run(client, wf, "e o reembolso?")["content"] == "recebi: REEMBOLSO e o reembolso?"
    assert _run(client, wf, "qual o horário?")["content"] == "caminho do padrão"


def test_entrada_original_e_por_texto(client: TestClient) -> None:
    triagem = _agent(client, "triagem", "claude-haiku-4-5")
    eco = _agent(client, "revisao", "claude-sonnet-4-6")
    anterior = _publish(
        client,
        "workflow",
        "padrao do agno",
        {"workflow": {"steps": [_step("triagem", triagem), _step("revisao", eco)]}},
    )
    assert _run(client, anterior, "minha pergunta")["content"] == "recebi: triagem: troca"

    original = _publish(
        client,
        "workflow",
        "pergunta original",
        {
            "workflow": {
                "steps": [_step("triagem", triagem), _step("revisao", eco, input="original")]
            }
        },
    )
    assert _run(client, original, "minha pergunta")["content"] == "recebi: minha pergunta"

    texto = _publish(
        client,
        "workflow",
        "por texto",
        {
            "workflow": {
                "steps": [
                    _step("triagem", triagem),
                    _step(
                        "revisao",
                        eco,
                        input="template",
                        template="Pedido: {entrada} | Triagem: {etapa:triagem} | {anterior}",
                    ),
                ]
            }
        },
    )
    assert (
        _run(client, texto, "x")["content"]
        == "recebi: Pedido: x | Triagem: triagem: troca | triagem: troca"
    )


def test_escrita_recusa_o_que_nao_roda(client: TestClient) -> None:
    eco = _agent(client, "eco2", "claude-sonnet-4-6")
    sem_texto = _publish(
        client,
        "workflow",
        "sem texto",
        {"workflow": {"steps": [_step("a", eco, input="template")]}},
    )
    assert sem_texto.status_code == 422
    etapa_inexistente = _publish(
        client,
        "workflow",
        "etapa inexistente",
        {"workflow": {"steps": [_step("a", eco, input="template", template="{etapa:b}")]}},
    )
    assert etapa_inexistente.status_code == 422 and "etapas que não existem" in (
        etapa_inexistente.text
    )
    router = _router(eco, eco)
    router["routes"][0]["step"]["review"] = {"when": "after"}
    router["default"]["name"] = "padrao2"
    revisado = _publish(
        client, "workflow", "revisao no roteador", {"workflow": {"steps": [router]}}
    )
    assert revisado.status_code == 422
