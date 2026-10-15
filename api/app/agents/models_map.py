import os

from agno.models.anthropic import Claude
from agno.models.base import Model
from agno.models.openai import OpenAIChat

from app.schemas.config import CapabilityFlags

_SUPPORTED: dict[str, type[Model]] = {
    "claude-opus-4-7": Claude,
    "claude-sonnet-4-6": Claude,
    "claude-haiku-4-5": Claude,
    "gpt-4o": OpenAIChat,
    "gpt-4o-mini": OpenAIChat,
    "o3": OpenAIChat,
    "o3-mini": OpenAIChat,
}


_THINKING_BUDGET_TOKENS = 4096


def resolve_model(model_id: str, capabilities: CapabilityFlags | None = None) -> Model:
    """Constrói instância de Model por request.

    Não retorna singleton — cada chamada produz um objeto novo. Isso garante
    que mudanças no model_id da config refletem imediatamente na próxima
    request, sem necessidade de reiniciar a aplicação (ADR-0006).

    Quando DEMO_REPLAY=true, retorna ReplayModel sem chamar o provedor real.

    De `capabilities`, só extended_thinking muda o modelo. Visão depende só do
    modelo e structured_output exige um output_schema, que o config ainda não tem.
    """
    if os.environ.get("DEMO_REPLAY", "").lower() in ("1", "true"):
        from app.agents.replay import ReplayModel

        return ReplayModel(id=model_id)

    cls = _SUPPORTED.get(model_id)
    if cls is None:
        raise ValueError(f"model_id '{model_id}' não suportado. Suportados: {sorted(_SUPPORTED)}")
    if capabilities is not None and capabilities.extended_thinking and cls is Claude:
        # budget abaixo do max_tokens padrão do Claude no Agno (8192)
        return Claude(
            id=model_id,
            thinking={"type": "enabled", "budget_tokens": _THINKING_BUDGET_TOKENS},
        )
    return cls(id=model_id)


def supported_models() -> list[str]:
    return sorted(_SUPPORTED)
