"""Evals do controle do run (ADR-0027).

Sem banco e sem rede: modelos falsos no lugar do provedor, rodando o Agent de verdade.
Errar aqui é deixar um laço de tool queimar o orçamento, repetir uma tool que já rodou
ao tentar de novo o provedor, esconder credencial errada atrás da reserva ou cobrar a
reserva pelo preço do principal.
"""

from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pytest
from agno.agent import Agent
from agno.exceptions import ModelProviderError, ModelRateLimitError
from agno.metrics import MessageMetrics
from agno.models.fallback import FallbackConfig
from agno.models.response import ModelResponse
from agno.run.base import RunStatus

from app.agents.replay import ReplayModel
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

LIMIT_MESSAGE = "Tool call limit reached"


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _messages(args: tuple[Any, ...], kwargs: dict[str, Any]) -> list[Any]:
    return list(kwargs.get("messages") or (args[0] if args else []))


def _tool_call(n: int) -> ModelResponse:
    return ModelResponse(
        role="assistant",
        tool_calls=[
            {
                "id": f"call_{n}",
                "type": "function",
                "function": {"name": "buscar_pedido", "arguments": "{}"},
            }
        ],
    )


@dataclass
class LoopingModel(ReplayModel):
    """Pede a mesma tool sem parar, até receber o aviso de limite do Agno."""

    calls: int = 0

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        self.calls += 1
        tools = [m for m in _messages(args, kwargs) if getattr(m, "role", None) == "tool"]
        if any(LIMIT_MESSAGE in str(m.content) for m in tools):
            return ModelResponse(role="assistant", content="parei no limite")
        if self.calls > 50:
            raise AssertionError("o limite não cortou o laço")
        return _tool_call(self.calls)


@dataclass
class FlakyModel(ReplayModel):
    """Pede a tool, cai com 503 nas `failures` chamadas seguintes e depois responde."""

    failures: int = 1
    status: int = 503
    calls: int = 0

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return _tool_call(1)
        if self.failures > 0:
            self.failures -= 1
            raise ModelProviderError("upstream", status_code=self.status, model_id=self.id)
        return ModelResponse(role="assistant", content="pedido 123 enviado")


@dataclass
class DownModel(ReplayModel):
    """Principal fora do ar: sempre o mesmo erro."""

    error: Exception = field(default_factory=lambda: ModelRateLimitError("limite"))

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise self.error


@dataclass
class PricedReply(FixedReplyModel):
    """Resposta fixa com entrada e saída medidas, para precificar pela tabela."""

    input_tokens: int = 0

    def _respond(self) -> ModelResponse:
        usage = MessageMetrics(
            input_tokens=self.input_tokens,
            output_tokens=self.tokens,
            total_tokens=self.input_tokens + self.tokens,
        )
        return ModelResponse(role="assistant", content=self.reply, response_usage=usage)


def _counter() -> tuple[list[int], Any]:
    ran: list[int] = []

    def buscar_pedido() -> str:
        """Busca o pedido do cliente."""
        ran.append(1)
        return "pedido 123: enviado"

    return ran, buscar_pedido


async def test_laco_de_tool_para_no_limite_com_resposta() -> None:
    ran, tool = _counter()
    agent = Agent(model=LoopingModel(id="claude-sonnet-4-6"), tools=[tool], tool_call_limit=3)
    out = await agent.arun("onde está meu pedido?")
    assert len(ran) == 3
    assert out.status == RunStatus.completed
    assert out.content == "parei no limite"


async def test_retry_repete_so_a_chamada_ao_modelo() -> None:
    ran, tool = _counter()
    model = FlakyModel(id="claude-sonnet-4-6", failures=2)
    model.retries, model.delay_between_retries = 2, 0
    out = await Agent(model=model, tools=[tool]).arun("onde está meu pedido?")
    assert out.status == RunStatus.completed
    assert out.content == "pedido 123 enviado"
    # a tool rodou uma vez: o 503 veio depois dela e só a chamada ao modelo se repetiu
    assert len(ran) == 1
    assert model.calls == 4


async def test_sem_retry_o_503_vira_erro() -> None:
    ran, tool = _counter()
    out = await Agent(model=FlakyModel(id="claude-sonnet-4-6"), tools=[tool]).arun("pedido?")
    assert out.status == RunStatus.error


async def test_429_cai_na_reserva_e_o_custo_sai_pela_tabela_dela() -> None:
    from app.pricing import answered_by, estimate_cost, run_cost

    reserva = PricedReply(id="gpt-4o", reply="resposta da reserva", tokens=200, input_tokens=1000)
    agent = Agent(
        model=DownModel(id="claude-sonnet-4-6"),
        fallback_config=FallbackConfig(on_error=[reserva], on_rate_limit=[reserva]),
    )
    out = await agent.arun("oi")
    assert out.status == RunStatus.completed
    assert out.content == "resposta da reserva"
    assert answered_by(out.metrics, "claude-sonnet-4-6") == "gpt-4o"
    assert run_cost(out.metrics, "claude-sonnet-4-6") == pytest.approx(
        estimate_cost("gpt-4o", 1000, 200)
    )


async def test_credencial_errada_nao_troca_de_modelo() -> None:
    reserva = FixedReplyModel(id="gpt-4o", reply="não devia responder")
    agent = Agent(
        model=DownModel(
            id="claude-sonnet-4-6", error=ModelProviderError("chave inválida", status_code=401)
        ),
        fallback_config=FallbackConfig(on_error=[reserva], on_rate_limit=[reserva]),
    )
    out = await agent.arun("oi")
    assert out.status == RunStatus.error
    assert out.content != "não devia responder"


async def test_resposta_estruturada_chega_como_objeto_e_valida() -> None:
    from app.agents.output_schema import schema_verdict

    schema = {
        "type": "object",
        "properties": {"categoria": {"enum": ["troca", "reembolso"]}},
        "required": ["categoria"],
    }
    model = FixedReplyModel(id="gpt-4o", reply='{"categoria": "troca"}')
    out = await Agent(model=model, output_schema=schema).arun("quero trocar")
    assert out.content == {"categoria": "troca"}
    assert schema_verdict(schema, out.content)["passed"] is True
