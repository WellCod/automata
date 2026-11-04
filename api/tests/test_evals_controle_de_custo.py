"""Evals do controle de custo no run (ADR-0031).

Sem banco e sem rede. Errar o teto deixa um laço de tools queimar dinheiro até o
limite de chamadas; errar o orçamento por quem chama barra o usuário errado, ou
deixa um token com bug gastar o orçamento do agente inteiro.
"""

from collections.abc import Generator
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from agno.agent import Agent
from agno.exceptions import InputCheckError
from agno.metrics import MessageMetrics
from agno.models.response import ModelResponse
from agno.run.base import RunStatus
from agno.tools.function import Function

from app.agents.replay import ReplayModel
from app.agents.run_cost import STOP_RUN_COST, CostCap, spent
from app.guardrails.input import BlockLog
from app.pricing import estimate_cost
from app.settings import get_settings

MODEL = "claude-sonnet-4-6"
CALL = estimate_cost(MODEL, 10_000, 200) or 0.0


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@dataclass
class Looper(ReplayModel):
    """Pede a tool sem parar; com `answer_after`, responde depois de N tools."""

    calls: int = 0
    answer_after: int | None = None

    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        self.calls += 1
        usage = MessageMetrics(input_tokens=10_000, output_tokens=200, total_tokens=10_200)
        if self.answer_after is not None and self.calls > self.answer_after:
            return ModelResponse(role="assistant", content="pronto", response_usage=usage)
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


def _tool(ran: list[int]) -> Function:
    async def buscar() -> str:
        """Busca."""
        ran.append(1)
        return "ok"

    return Function.from_callable(buscar)


async def _run(limit: float, answer_after: int | None = None) -> tuple[Any, Looper, BlockLog, int]:
    log, ran = BlockLog(), []
    model = Looper(id=MODEL, answer_after=answer_after)
    agent = Agent(
        model=model,
        tools=[_tool(ran)],
        tool_hooks=CostCap(limit, MODEL, log).hooks(),
        tool_call_limit=100,
    )
    out = await agent.arun("?")
    return out, model, log, len(ran)


# --- teto por run ---


async def test_criterio_de_aceite_teto_de_5_centavos() -> None:
    out, model, log, ran = await _run(0.05)
    assert out.status == RunStatus.completed
    assert log.stop_reason == STOP_RUN_COST
    # passa do teto no máximo pelo custo de uma chamada ao modelo
    assert spent(out.messages, MODEL) <= 0.05 + CALL
    assert ran == model.calls - 1


@pytest.mark.parametrize("calls", [1, 2, 5])
async def test_teto_corta_na_chamada_certa(calls: int) -> None:
    out, model, log, _ = await _run(calls * CALL)
    assert model.calls == calls
    assert log.stop_reason == STOP_RUN_COST


async def test_abaixo_do_teto_o_run_termina_normal() -> None:
    out, model, log, ran = await _run(10 * CALL, answer_after=3)
    assert out.content == "pronto"
    assert (model.calls, ran, log.stop_reason) == (4, 3, None)


def test_modelo_sem_preco_nao_para_nada() -> None:
    # sem preço na tabela o custo é desconhecido: o teto não inventa valor
    message = SimpleNamespace(role="assistant", metrics=MessageMetrics(input_tokens=10**9))
    assert spent([message], "modelo-sem-preco") == 0.0


# --- orçamento por quem chama ---


def _budget(limit: float, hard_stop: bool, warn: int = 80) -> Any:
    return SimpleNamespace(monthly_usd=Decimal(str(limit)), hard_stop=hard_stop, warn_percent=warn)


@pytest.mark.parametrize(
    ("spent_usd", "level"),
    [(0.0, "ok"), (7.99, "ok"), (8.0, "warning"), (9.99, "warning"), (10.0, "exceeded")],
)
def test_nivel_do_orcamento(spent_usd: float, level: str) -> None:
    from app.caller_budget import state_for

    assert state_for(_budget(10, False), spent_usd).level == level


@pytest.mark.parametrize(
    ("subject", "budget", "spent_usd", "blocked"),
    [
        ("integration:a", _budget(1, True), 1.0, True),
        ("integration:a", _budget(1, True), 0.99, False),
        # sem bloqueio o orçamento só mede
        ("integration:a", _budget(1, False), 50.0, False),
        # sem orçamento cadastrado, nada barra
        ("integration:b", None, 50.0, False),
        # run sem usuário (anônimo da demo): nada a conferir
        (None, _budget(1, True), 50.0, False),
    ],
)
async def test_bloqueio_so_de_quem_estourou_com_bloqueio(
    monkeypatch: pytest.MonkeyPatch,
    subject: str | None,
    budget: Any,
    spent_usd: float,
    blocked: bool,
) -> None:
    import app.caller_budget as caller

    monkeypatch.setattr(caller, "_cached_budget", lambda s: budget if s == subject else None)
    monkeypatch.setattr(caller, "_cached_spend", lambda s: spent_usd)
    log = BlockLog()
    guard = caller.CallerBudgetGuardrail(log)
    context = SimpleNamespace(user_id=subject)
    if blocked:
        with pytest.raises(InputCheckError):
            await guard.async_check(SimpleNamespace(), context)  # type: ignore[arg-type]
        assert log.last is not None and log.last.detail["scope"] == "caller"
    else:
        await guard.async_check(SimpleNamespace(), context)  # type: ignore[arg-type]
        assert log.blocks == []
