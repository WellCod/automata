from dataclasses import dataclass

from app.schemas.config import CapabilityFlags


@dataclass(frozen=True)
class ModelCapabilities:
    extended_thinking: bool = False
    structured_output: bool = False
    vision: bool = False


_CAPABILITIES: dict[str, ModelCapabilities] = {
    "claude-opus-4-7": ModelCapabilities(
        extended_thinking=True, structured_output=True, vision=True
    ),
    "claude-sonnet-4-6": ModelCapabilities(
        extended_thinking=True, structured_output=True, vision=True
    ),
    "claude-haiku-4-5": ModelCapabilities(
        extended_thinking=False, structured_output=True, vision=True
    ),
    "gpt-4o": ModelCapabilities(extended_thinking=False, structured_output=True, vision=True),
    "gpt-4o-mini": ModelCapabilities(extended_thinking=False, structured_output=True, vision=True),
    "o3": ModelCapabilities(extended_thinking=False, structured_output=True, vision=False),
    "o3-mini": ModelCapabilities(extended_thinking=False, structured_output=True, vision=False),
}


def get_capabilities(model_id: str) -> ModelCapabilities:
    caps = _CAPABILITIES.get(model_id)
    if caps is None:
        raise ValueError(
            f"model_id '{model_id}' não suportado. Suportados: {sorted(_CAPABILITIES)}"
        )
    return caps


def validate_capabilities(model_id: str, requested: CapabilityFlags) -> list[str]:
    """Retorna lista de erros de validação; lista vazia significa válido."""
    caps = get_capabilities(model_id)
    errors: list[str] = []
    if requested.extended_thinking and not caps.extended_thinking:
        errors.append(f"'{model_id}' não suporta extended_thinking")
    if requested.structured_output and not caps.structured_output:
        errors.append(f"'{model_id}' não suporta structured_output")
    if requested.vision and not caps.vision:
        errors.append(f"'{model_id}' não suporta vision")
    return errors


def all_capabilities() -> dict[str, ModelCapabilities]:
    return dict(_CAPABILITIES)
