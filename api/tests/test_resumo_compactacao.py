"""Modelo próprio para o resumo da compactação (ADR-0035)."""

from types import SimpleNamespace

import pytest

from app.agents.factory import compaction_for
from app.pricing import estimate_cost, run_cost
from app.schemas.config import ConfigPayload
from app.services.config import ConfigService


def _payload(**conversation: object) -> ConfigPayload:
    return ConfigPayload.model_validate(
        {
            "model_id": "claude-sonnet-4-6",
            "conversation": {"compaction": True, **conversation},
        }
    )


def test_resumo_sai_do_modelo_escolhido(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agents.factory as factory

    monkeypatch.setattr(factory, "demo_replay", lambda: False)
    compaction = compaction_for(_payload(summary_model="claude-haiku-4-5"))
    assert compaction is not None and compaction.model is not None
    assert getattr(compaction.model, "id", None) == "claude-haiku-4-5"
    # sem modelo próprio, o Agno usa o do agente
    plain = compaction_for(_payload())
    assert plain is not None and plain.model is None


def test_modo_demo_resume_com_o_modelo_do_agente(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agents.factory as factory

    monkeypatch.setattr(factory, "demo_replay", lambda: True)
    compaction = compaction_for(_payload(summary_model="claude-haiku-4-5"))
    assert compaction is not None and compaction.model is None


def test_modelo_do_resumo_so_da_matriz() -> None:
    assert ConfigService._compression_errors(_payload(summary_model="claude-haiku-4-5")) == []
    [error] = ConfigService._compression_errors(_payload(summary_model="inventado"))
    assert error.startswith("modelo do resumo da conversa")


def test_custo_do_run_soma_o_resumo_pelo_preco_do_modelo_dele() -> None:
    metrics = SimpleNamespace(
        cost=None,
        input_tokens=11_000,
        output_tokens=700,
        details={
            "model": [
                SimpleNamespace(
                    id="claude-sonnet-4-6", cost=None, input_tokens=1_000, output_tokens=200
                )
            ],
            "compaction_model": [
                SimpleNamespace(
                    id="claude-haiku-4-5", cost=None, input_tokens=10_000, output_tokens=500
                )
            ],
        },
    )
    expected = (estimate_cost("claude-sonnet-4-6", 1_000, 200) or 0) + (
        estimate_cost("claude-haiku-4-5", 10_000, 500) or 0
    )
    assert run_cost(metrics, "claude-sonnet-4-6") == pytest.approx(expected)
    # pelo preço do agente, o resumo sairia mais caro
    assert expected < (estimate_cost("claude-sonnet-4-6", 11_000, 700) or 0)
