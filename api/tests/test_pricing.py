"""Custo estimado pela tabela de preços (ADR-0021): Anthropic e OpenAI só devolvem tokens."""

import pytest

from app import pricing
from app.pricing import cost_or_estimate, estimate_cost
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _limpa_cache() -> None:
    pricing._overrides.cache_clear()
    get_settings.cache_clear()


def test_custo_pelos_tokens_com_o_preco_da_tabela() -> None:
    # haiku: US$ 1 por milhão de entrada e US$ 5 por milhão de saída
    assert estimate_cost("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)
    assert estimate_cost("claude-haiku-4-5", 2_000, 1_000) == pytest.approx(0.007)


def test_custo_informado_pelo_provedor_vale_mais_que_a_estimativa() -> None:
    assert cost_or_estimate(0.42, "claude-haiku-4-5", 1_000_000, 1_000_000) == 0.42
    assert cost_or_estimate(None, "claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)


def test_modelo_sem_preco_nao_inventa_valor() -> None:
    assert estimate_cost("modelo-inventado", 1_000, 1_000) is None
    assert estimate_cost(None, 1_000, 1_000) is None


def test_model_prices_sobrescreve_e_invalido_cai_na_tabela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    monkeypatch.setenv("MODEL_PRICES", '{"claude-haiku-4-5": {"input": 0.5, "output": 2}}')
    get_settings.cache_clear()
    assert estimate_cost("claude-haiku-4-5", 1_000_000, 1_000_000) == pytest.approx(2.5)
    # o resto da tabela continua
    assert estimate_cost("gpt-4o", 1_000_000, 0) == pytest.approx(2.5)

    monkeypatch.setenv("MODEL_PRICES", "não é json")
    get_settings.cache_clear()
    pricing._overrides.cache_clear()
    assert estimate_cost("claude-haiku-4-5", 1_000_000, 0) == pytest.approx(1.0)
