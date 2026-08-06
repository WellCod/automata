from agno.models.anthropic import Claude
from agno.models.base import Model
from agno.models.openai import OpenAIChat

_SUPPORTED: dict[str, type[Model]] = {
    "claude-opus-4-7": Claude,
    "claude-sonnet-4-6": Claude,
    "claude-haiku-4-5": Claude,
    "gpt-4o": OpenAIChat,
    "gpt-4o-mini": OpenAIChat,
    "o3": OpenAIChat,
    "o3-mini": OpenAIChat,
}


def resolve_model(model_id: str) -> Model:
    """Constrói instância de Model por request.

    Não retorna singleton — cada chamada produz um objeto novo. Isso garante
    que mudanças no model_id da config refletem imediatamente na próxima
    request, sem necessidade de reiniciar a aplicação (ADR-0006).
    """
    cls = _SUPPORTED.get(model_id)
    if cls is None:
        raise ValueError(f"model_id '{model_id}' não suportado. Suportados: {sorted(_SUPPORTED)}")
    return cls(id=model_id)


def supported_models() -> list[str]:
    return sorted(_SUPPORTED)
