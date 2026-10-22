"""Preço por modelo e custo estimado pelos tokens (ADR-0021).

O Agno só preenche `metrics.cost` quando o provedor informa o valor na resposta;
Anthropic e OpenAI devolvem tokens, não custo. Sem a tabela, o custo de um run
real ficava vazio, e com ele o analytics e o orçamento.

Preços de referência em dólar por milhão de tokens, da lista pública de cada
provedor em 2026-10. `MODEL_PRICES` sobrescreve modelo a modelo, para contrato
com desconto ou preço que mudou:

    MODEL_PRICES='{"claude-sonnet-4-6": {"input": 2.5, "output": 12}}'
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache

from pydantic import ValidationError

from app.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelPrice:
    # dólar por milhão de tokens
    input: float
    output: float


_PRICES: dict[str, ModelPrice] = {
    "claude-opus-4-7": ModelPrice(input=5.0, output=25.0),
    "claude-sonnet-4-6": ModelPrice(input=3.0, output=15.0),
    "claude-haiku-4-5": ModelPrice(input=1.0, output=5.0),
    "gpt-4o": ModelPrice(input=2.5, output=10.0),
    "gpt-4o-mini": ModelPrice(input=0.15, output=0.6),
    "o3": ModelPrice(input=2.0, output=8.0),
    "o3-mini": ModelPrice(input=1.1, output=4.4),
}


@lru_cache(maxsize=1)
def _overrides(raw: str) -> dict[str, ModelPrice]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        return {
            model: ModelPrice(input=float(p["input"]), output=float(p["output"]))
            for model, p in data.items()
        }
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        # preço errado não pode derrubar o run: vale a tabela e fica o aviso
        logger.warning("MODEL_PRICES inválido; usando a tabela", extra={"error": str(exc)})
        return {}


def _raw_overrides() -> str:
    try:
        return get_settings().model_prices
    except ValidationError:
        # sem banco e chaves configurados (teste de unidade, script): só a tabela
        return ""


def prices() -> dict[str, ModelPrice]:
    return {**_PRICES, **_overrides(_raw_overrides())}


def estimate_cost(model_id: str | None, input_tokens: int, output_tokens: int) -> float | None:
    """Custo pelos tokens; None para modelo sem preço (não inventa um valor)."""
    if model_id is None:
        return None
    price = prices().get(model_id)
    if price is None:
        return None
    return (input_tokens * price.input + output_tokens * price.output) / 1_000_000


def cost_or_estimate(
    reported: float | None, model_id: str | None, input_tokens: int, output_tokens: int
) -> float | None:
    """O custo informado pelo provedor vale; sem ele, a estimativa pela tabela."""
    if reported is not None:
        return reported
    return estimate_cost(model_id, input_tokens, output_tokens)
