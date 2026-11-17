"""Modo de extended thinking por modelo: o Claude 4.7 recusa `budget_tokens` com 400."""

import json

import pytest

from app.agents.extra_models import _parse
from app.agents.models_map import resolve_model
from app.schemas.config import CapabilityFlags

THINKING = CapabilityFlags(extended_thinking=True)


@pytest.fixture(autouse=True)
def _sem_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_REPLAY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-teste")


@pytest.mark.parametrize("model_id", ["claude-opus-4-7", "claude-sonnet-4-6"])
def test_matriz_pensa_no_modo_adaptativo(model_id: str) -> None:
    model = resolve_model(model_id, THINKING)
    assert model.thinking == {"type": "adaptive", "display": "summarized"}  # type: ignore[attr-defined]


def test_sem_extended_thinking_nao_manda_thinking() -> None:
    assert resolve_model("claude-sonnet-4-6").thinking is None  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-sonnet-4-5", {"type": "enabled", "budget_tokens": 4096}),
        ("claude-opus-4-8", {"type": "adaptive", "display": "summarized"}),
    ],
)
def test_extra_usa_o_orcamento_so_onde_ele_vale(
    monkeypatch: pytest.MonkeyPatch, model: str, expected: dict[str, object]
) -> None:
    raw = json.dumps([{"id": model, "provider": "anthropic", "extended_thinking": True}])
    monkeypatch.setenv("EXTRA_MODELS", raw)
    _parse.cache_clear()
    try:
        assert resolve_model(model, THINKING).thinking == expected  # type: ignore[attr-defined]
    finally:
        _parse.cache_clear()
