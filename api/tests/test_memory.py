"""Memória do usuário entre sessões (ADR-0025): só do agente, só do usuário, mascarada."""

import os
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from agno.db.schemas.memory import UserMemory
from agno.models.response import ModelResponse
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.settings import get_settings

FACT = "Veste camiseta tamanho M"


@dataclass
class MemoryAwareModel(ReplayModel):
    """Diz se a memória chegou nas mensagens; no pedido de extração, não guarda nada."""

    def _respond(self, messages: Any) -> ModelResponse:
        texts = " ".join(str(getattr(m, "content", "") or "") for m in messages or [])
        return ModelResponse(
            role="assistant", content="lembro do tamanho" if FACT in texts else "não lembro"
        )

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        return self._respond(kwargs.get("messages"))

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        yield self._respond(kwargs.get("messages"))


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
        factory.resolve_model = lambda *a, **k: MemoryAwareModel(id="claude-haiku-4-5")  # type: ignore[assignment]
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        factory.resolve_model = original
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _agent(client: TestClient, name: str, memory: dict[str, Any], kind: str = "agent") -> Any:
    body = {"name": name, "description": "x"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": kind}).json()["id"]
    return client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={**body, "payload": {"model_id": "claude-haiku-4-5", "memory": memory}},
    ), config_id


def _published(client: TestClient, name: str, memory: dict[str, Any]) -> str:
    resp, config_id = _agent(client, name, memory)
    resp.raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _remember(agent: str, user: str, text: str = FACT, message: str | None = None) -> None:
    from app.agents.memory import memory_db

    memory_db().upsert_user_memory(
        UserMemory(memory_id=str(uuid4()), user_id=user, agent_id=agent, memory=text, input=message)
    )


def _ask(client: TestClient, agent: str, user: str | None) -> str:
    data = {"message": "que tamanho eu visto?", "stream": "false"}
    if user:
        data["user_id"] = user
    resp = client.post(f"/agents/{agent}/runs", data=data)
    assert resp.status_code == 200, resp.text
    return str(resp.json()["content"])


def test_memoria_so_do_agente_e_so_do_usuario(client: TestClient) -> None:
    loja = _published(client, "loja", {"enabled": True})
    cobranca = _published(client, "cobrança", {"enabled": True})
    desligada = _published(client, "sem memória", {"enabled": False})
    _remember(loja, "cliente-1")
    _remember(desligada, "cliente-1")

    assert _ask(client, loja, "cliente-1") == "lembro do tamanho"
    # outro agente com memória ligada não vê o que a loja guardou
    assert _ask(client, cobranca, "cliente-1") == "não lembro"
    # outro usuário no mesmo agente também não
    assert _ask(client, loja, "cliente-2") == "não lembro"
    # sem usuário, sem memória: o "default" do Agno juntaria pessoas diferentes
    assert _ask(client, loja, None) == "não lembro"
    # memória desligada não lê nem o que já estava gravado
    assert _ask(client, desligada, "cliente-1") == "não lembro"


def test_dado_pessoal_sai_mascarado_da_memoria(client: TestClient) -> None:
    from app.agents.memory import memory_db

    agent = _published(client, "mascarado", {"enabled": True})
    _remember(
        agent,
        "cliente-3",
        text="CPF 529.982.247-25 e e-mail ana@exemplo.com",
        message="meu cpf é 529.982.247-25",
    )
    [saved] = memory_db().get_user_memories(user_id="cliente-3", agent_id=agent)
    assert isinstance(saved, UserMemory)
    assert "529.982.247-25" not in saved.memory and "ana@exemplo.com" not in saved.memory
    assert saved.input is not None and "529.982.247-25" not in saved.input


def test_memoria_so_em_agente(client: TestClient) -> None:
    resp, _ = _agent(client, "time com memória", {"enabled": True}, kind="team")
    assert resp.status_code in (400, 422)
    assert "só agente guarda memória do usuário" in resp.text
    resp, _ = _agent(client, "retenção longa", {"enabled": True, "retention_days": 400})
    assert resp.status_code == 422


def test_suite_de_testes_roda_sem_memoria() -> None:
    from app.agents.memory import memory_kwargs
    from app.schemas.config import MemorySettings

    on = MemorySettings(enabled=True, instructions="lembre o tamanho")
    assert memory_kwargs("a", on, None) == {}
    assert memory_kwargs("a", MemorySettings(), "cliente") == {}
    kwargs = memory_kwargs("a", on, "cliente")
    assert kwargs["update_memory_on_run"] is True
    manager = kwargs["memory_manager"]
    assert manager.agent_id == "a"
    assert manager.memory_capture_instructions.startswith("lembre o tamanho")
    assert "Nunca guarde documento" in manager.memory_capture_instructions
