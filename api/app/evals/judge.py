"""Modelo do juiz com consumo medido (ADR-0015).

O `AgentAsJudgeEval` do Agno monta o agente avaliador por dentro e não devolve as
métricas dele. O medidor embrulha o `ainvoke` da instância: no Agno 3.1.8 todo
provedor devolve dali um `ModelResponse` já com `response_usage`, e o retry do
modelo chama esse mesmo método. O juiz roda sem stream, então o caminho de
`ainvoke_stream` não é usado.
"""

from dataclasses import dataclass
from typing import Any

from agno.models.base import Model


@dataclass
class JudgeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None

    def add(self, usage: Any) -> None:
        self.input_tokens += int(getattr(usage, "input_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "output_tokens", 0) or 0)
        self.total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
        cost = getattr(usage, "cost", None)
        if cost is not None:
            self.cost = (self.cost or 0.0) + float(cost)


def metered(model: Model) -> tuple[Model, JudgeUsage]:
    """Embrulha `ainvoke` (juiz) e `invoke` (HyDE, ADR-0017) da instância."""
    usage = JudgeUsage()
    ainvoke = model.ainvoke
    invoke = model.invoke

    def count(response: Any) -> Any:
        if getattr(response, "response_usage", None) is not None:
            usage.add(response.response_usage)
        return response

    async def counting_async(*args: Any, **kwargs: Any) -> Any:
        return count(await ainvoke(*args, **kwargs))

    def counting(*args: Any, **kwargs: Any) -> Any:
        return count(invoke(*args, **kwargs))

    # atributo da instância: se o Agno copiar o modelo, a função ainda soma no mesmo medidor
    model.ainvoke = counting_async  # type: ignore[method-assign]
    model.invoke = counting  # type: ignore[method-assign]
    return model, usage
