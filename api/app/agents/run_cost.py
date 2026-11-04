"""Teto de custo por run (ADR-0031).

Antes de cada tool, o gancho soma os tokens das mensagens do assistente no run e
precifica pela tabela do modelo do agente. Passou do teto, a tool não roda e o
`StopAgentRun` encerra o laço do modelo sem erro. O Agno não chama o modelo de novo
depois disso, então o tracking põe a mensagem do teto no lugar da resposta vazia.
"""

from collections.abc import Callable
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from agno.exceptions import StopAgentRun
from agno.run import RunContext

from app.guardrails.input import BlockLog
from app.pricing import estimate_cost

STOP_RUN_COST = "run_cost_limit"
COST_LIMIT_MESSAGE = (
    "Parei antes de terminar: esta conversa chegou ao limite de custo por resposta. "
    "Tente de novo com um pedido mais curto ou mais específico."
)


def spent(messages: list[Any] | None, model_id: str) -> float:
    """Custo das chamadas ao modelo já feitas no run, pela tabela de preços."""
    input_tokens = output_tokens = 0
    for message in messages or []:
        if getattr(message, "role", None) != "assistant":
            continue
        metrics = getattr(message, "metrics", None)
        input_tokens += int(getattr(metrics, "input_tokens", 0) or 0)
        output_tokens += int(getattr(metrics, "output_tokens", 0) or 0)
    return estimate_cost(model_id, input_tokens, output_tokens) or 0.0


@dataclass
class CostCap:
    limit_usd: float
    model_id: str
    log: BlockLog

    def check(self, run_context: RunContext | None) -> None:
        cost = spent(run_context.messages if run_context else None, self.model_id)
        if cost < self.limit_usd:
            return
        self.log.stop_reason = STOP_RUN_COST
        raise StopAgentRun(
            f"teto de custo do run: US$ {cost:.4f} de US$ {self.limit_usd:.2f}",
            agent_message="Limite de custo do run atingido: encerre sem chamar mais tools.",
        )

    def hooks(self) -> list[Callable[..., Any]]:
        def cap_sync(
            function_call: Callable[..., Any],
            arguments: Any,
            run_context: RunContext | None = None,
        ) -> Any:
            self.check(run_context)
            return function_call(**arguments)

        async def cap_async(
            function_call: Callable[..., Any],
            arguments: Any,
            run_context: RunContext | None = None,
        ) -> Any:
            self.check(run_context)
            result = function_call(**arguments)
            return await result if isawaitable(result) else result

        # o assíncrono por fora, como no exame de tool: a cadeia síncrona descarta o async
        return [cap_async, cap_sync]
