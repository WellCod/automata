"""Testes da resolução de modelo e da factory.

Não chama LLM real — verifica apenas que os objetos corretos são construídos.
"""

import pytest
from agno.models.anthropic import Claude
from agno.models.openai import OpenAIChat

from app.agents.models_map import resolve_model, supported_models


def test_resolve_claude() -> None:
    model = resolve_model("claude-sonnet-4-6")
    assert isinstance(model, Claude)
    assert model.id == "claude-sonnet-4-6"


def test_resolve_openai() -> None:
    model = resolve_model("gpt-4o")
    assert isinstance(model, OpenAIChat)
    assert model.id == "gpt-4o"


def test_resolve_cria_instancia_nova_por_chamada() -> None:
    """Cada chamada retorna um objeto diferente — sem singleton."""
    m1 = resolve_model("claude-sonnet-4-6")
    m2 = resolve_model("claude-sonnet-4-6")
    assert m1 is not m2


def test_resolve_model_desconhecido() -> None:
    with pytest.raises(ValueError, match="não suportado"):
        resolve_model("modelo-inventado")


def test_supported_models_retorna_lista_ordenada() -> None:
    models = supported_models()
    assert models == sorted(models)
    assert "claude-sonnet-4-6" in models
    assert "gpt-4o" in models
