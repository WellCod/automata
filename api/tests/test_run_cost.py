"""Teto de custo por run (ADR-0031): a parada, a resposta e o registro no run."""

import os
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from agno.agent import Agent
from agno.metrics import MessageMetrics
from agno.models.response import ModelResponse
from agno.run.base import RunStatus
from agno.tools.function import Function
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.agents.run_cost import COST_LIMIT_MESSAGE, STOP_RUN_COST, CostCap, spent
from app.guardrails.input import BlockLog
from app.pricing import estimate_cost
from app.schemas.config import ConfigPayload
from app.settings import get_settings

MODEL = "claude-sonnet-4-6"


@dataclass
class Looper(ReplayModel):
    """Pede a mesma tool sem parar; cada chamada custa 10 mil tokens de entrada."""

    calls: int = 0

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        self.calls += 1
        usage = MessageMetrics(input_tokens=10_000, output_tokens=200, total_tokens=10_200)
        return ModelResponse(
            role="assistant",
            response_usage=usage,
            tool_calls=[
                {
                    "id": f"c{self.calls}",
                    "type": "function",
                    "function": {"name": "buscar", "arguments": "{}"},
                }
            ],
        )

    def invoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise AssertionError("o run é assíncrono")


def _tool(ran: list[int]) -> Function:
    async def buscar() -> str:
        """Busca o pedido."""
        ran.append(1)
        return "pedido em trânsito"

    return Function.from_callable(buscar)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql://x"))
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- unidade ---


def test_teto_fora_da_faixa_recusado() -> None:
    for bad in (0, 0.001, 101):
        with pytest.raises(ValidationError):
            ConfigPayload.model_validate({"model_id": MODEL, "run": {"max_cost_usd": bad}})
    assert ConfigPayload.model_validate({"model_id": MODEL}).run.max_cost_usd is None


def test_custo_somado_so_das_mensagens_do_assistente() -> None:
    from agno.models.message import Message

    def msg(role: str, tokens: int) -> Message:
        message = Message(role=role, content="x")
        message.metrics = MessageMetrics(input_tokens=tokens, output_tokens=100)
        return message

    messages = [
        msg("user", 999_999),
        msg("assistant", 1000),
        msg("tool", 5),
        msg("assistant", 2000),
    ]
    assert spent(messages, MODEL) == pytest.approx(estimate_cost(MODEL, 3000, 200))
    assert spent(None, MODEL) == 0.0


async def test_teto_encerra_o_laco_antes_do_limite_de_tools() -> None:
    log = BlockLog()
    # cada chamada custa o mesmo: o teto cabe em três
    limit = 3 * (estimate_cost(MODEL, 10_000, 200) or 0)
    model = Looper(id=MODEL)
    ran: list[int] = []
    agent = Agent(
        model=model,
        tools=[_tool(ran)],
        tool_hooks=CostCap(limit, MODEL, log).hooks(),
        tool_call_limit=50,
    )
    out = await agent.arun("onde está o pedido?")
    assert out.status == RunStatus.completed
    assert model.calls == 3 and len(ran) == 2
    assert log.stop_reason == STOP_RUN_COST
    # a parada é entre uma chamada e a próxima tool: passa no máximo por uma chamada
    assert spent(out.messages, MODEL) <= limit + (estimate_cost(MODEL, 10_000, 200) or 0)


def test_factory_poe_o_teto_antes_do_exame_de_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.factory import ResolvedVersion, agent_from

    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    payload = ConfigPayload.model_validate(
        {"model_id": MODEL, "run": {"max_cost_usd": 0.5}, "guardrails": {"tool_results": {}}}
    )
    agent = agent_from(UUID(int=1), ResolvedVersion("a", "Use para a", payload), tracked=False)
    names = [h.__name__ for h in agent.tool_hooks or []]
    assert names == ["cap_async", "cap_sync", "screen_async", "screen_sync"]
    plain = ConfigPayload.model_validate({"model_id": MODEL})
    assert (
        agent_from(UUID(int=2), ResolvedVersion("b", "Use", plain), tracked=False).tool_hooks
        is None
    )


# --- integração: o run gravado pela factory ---


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from app.main import create_app

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


async def test_run_parado_pelo_teto_responde_e_registra_o_motivo(client: TestClient) -> None:
    from app.agents.factory import ResolvedVersion, agent_from
    from app.db import get_engine
    from app.models.run import AgentRun

    created = client.post("/api/v1/configs", json={"name": "pedidos", "description": "x"})
    config_id = UUID(created.json()["id"])
    payload = ConfigPayload.model_validate({"model_id": MODEL, "run": {"max_cost_usd": 0.05}})
    ran: list[int] = []
    resolved = ResolvedVersion("pedidos", "x", payload, knowledge_tools=[_tool(ran)])
    agent = agent_from(config_id, resolved, tracked=True)
    agent.model = Looper(id=MODEL)
    out = await agent.arun("onde está o pedido?", user_id="ana")
    assert out.status == RunStatus.completed
    assert out.content == COST_LIMIT_MESSAGE
    with Session(get_engine()) as session:
        run = session.query(AgentRun).filter(AgentRun.run_id == out.run_id).one()
        assert (run.status, run.stop_reason, run.error) == ("success", STOP_RUN_COST, None)
    [listed] = client.get(f"/api/v1/configs/{config_id}/runs").json()["items"]
    assert listed["stop_reason"] == STOP_RUN_COST
    # parada pelo teto não é erro
    metrics = client.get(f"/api/v1/configs/{config_id}/metrics").json()
    assert metrics["error_rate"] == 0
