import os
from typing import Any

from agno.models.anthropic import Claude
from agno.models.base import Model
from agno.models.openai import OpenAIChat

from app.agents.extra_models import ExtraModel, extra_models
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

# Claude 4.6 em diante pensa no modo adaptativo, e o 4.7 recusa `budget_tokens` com 400.
# `summarized` devolve o resumo do raciocínio; sem ele os blocos de thinking vêm vazios
_ADAPTIVE_THINKING: dict[str, Any] = {"type": "adaptive", "display": "summarized"}
_ADAPTIVE_MODELS = {"claude-opus-4-7", "claude-sonnet-4-6"}


def _thinking(model_name: str) -> dict[str, Any]:
    """Modo de extended thinking que o modelo aceita.

    Da matriz, os que documentam o adaptativo; de fora dela (EXTRA_MODELS), o orçamento
    só onde o Agno sabe que ele ainda vale (Claude 4.5 e anteriores).
    """
    from agno.utils.models.claude import supports_thinking_budget

    if model_name in _ADAPTIVE_MODELS or not supports_thinking_budget(model_name):
        return dict(_ADAPTIVE_THINKING)
    # orçamento abaixo do max_tokens padrão do Claude no Agno (8192)
    return {"type": "enabled", "budget_tokens": _THINKING_BUDGET_TOKENS}


# Os SDKs esperam 600 s com 2 novas tentativas: um provedor que aceita a conexão e não
# responde segurava cada run, mensagem de canal e caso de suíte por até 30 min (OPS-03).
# Com 120 s e uma nova tentativa, o pior caso fica em 4 min e o erro aparece
PROVIDER_TIMEOUT_SECONDS = 120.0
PROVIDER_SDK_RETRIES = 1


def demo_replay() -> bool:
    """Modo demo: respostas gravadas no lugar do provedor (ADR-0008)."""
    return os.environ.get("DEMO_REPLAY", "").lower() in ("1", "true")


def resolve_model(model_id: str, capabilities: CapabilityFlags | None = None) -> Model:
    """Constrói instância de Model por request.

    Não retorna singleton — cada chamada produz um objeto novo. Isso garante
    que mudanças no model_id da config refletem imediatamente na próxima
    request, sem necessidade de reiniciar a aplicação (ADR-0006).

    Quando DEMO_REPLAY=true, retorna ReplayModel sem chamar o provedor real.

    De `capabilities`, só extended_thinking muda o modelo. Visão depende só do
    modelo e structured_output exige um output_schema, que o config ainda não tem.
    """
    if demo_replay():
        from app.agents.replay import ReplayModel

        return ReplayModel(id=model_id)

    extra = extra_models().get(model_id)
    if extra is not None:
        return _from_extra(extra, capabilities)
    cls = _SUPPORTED.get(model_id)
    if cls is None:
        raise ValueError(f"model_id '{model_id}' não suportado. Suportados: {supported_models()}")
    if capabilities is not None and capabilities.extended_thinking and cls is Claude:
        return Claude(
            id=model_id,
            thinking=_thinking(model_id),
            timeout=PROVIDER_TIMEOUT_SECONDS,
            client_params={"max_retries": PROVIDER_SDK_RETRIES},
        )
    if cls is Claude:
        return Claude(
            id=model_id,
            timeout=PROVIDER_TIMEOUT_SECONDS,
            client_params={"max_retries": PROVIDER_SDK_RETRIES},
        )
    return OpenAIChat(
        id=model_id, timeout=PROVIDER_TIMEOUT_SECONDS, max_retries=PROVIDER_SDK_RETRIES
    )


def _from_extra(extra: ExtraModel, capabilities: CapabilityFlags | None) -> Model:
    """Modelo do EXTRA_MODELS, com o mesmo prazo e as mesmas tentativas da matriz (ARQ-02)."""
    name = extra.model or extra.id
    key = os.environ.get(extra.key_env)
    if extra.provider == "anthropic":
        params: dict[str, object] = {"max_retries": PROVIDER_SDK_RETRIES}
        if extra.base_url:
            params["base_url"] = extra.base_url
        thinking = (
            _thinking(name) if capabilities is not None and capabilities.extended_thinking else None
        )
        return Claude(
            id=name,
            api_key=key,
            thinking=thinking,
            timeout=PROVIDER_TIMEOUT_SECONDS,
            client_params=params,
        )
    return OpenAIChat(
        id=name,
        api_key=key,
        base_url=extra.base_url,
        timeout=PROVIDER_TIMEOUT_SECONDS,
        max_retries=PROVIDER_SDK_RETRIES,
    )


def provider_of(model_id: str) -> str:
    """ "anthropic" ou "openai", pela classe do modelo na matriz ou pelo EXTRA_MODELS."""
    extra = extra_models().get(model_id)
    if extra is not None:
        return extra.provider
    return "anthropic" if _SUPPORTED.get(model_id) is Claude else "openai"


def key_env_of(model_id: str) -> str:
    """Variável com a chave do provedor do modelo."""
    extra = extra_models().get(model_id)
    if extra is not None:
        return extra.key_env
    return "ANTHROPIC_API_KEY" if provider_of(model_id) == "anthropic" else "OPENAI_API_KEY"


def supported_models() -> list[str]:
    return sorted({*_SUPPORTED, *extra_models()})
