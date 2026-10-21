"""Evals do custo estimado, do orçamento e do pico de erro (ADR-0021).

Sem banco e sem rede: rodam em todo PR. Errar o custo subestima o orçamento;
errar o nível avisa tarde ou barra cedo; errar o pico enche o canal ou cala um
agente quebrado.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from agno.exceptions import InputCheckError
from agno.run.agent import RunInput

from app import alerts, budget
from app.guardrails.input import BlockLog
from app.pricing import _PRICES, cost_or_estimate, estimate_cost


def test_tabela_de_precos_coerente() -> None:
    for model, price in _PRICES.items():
        assert price.input > 0 and price.output > 0, model
        # saída custa pelo menos a entrada em todo provedor da tabela
        assert price.output >= price.input, model


@pytest.mark.parametrize(
    ("model", "inp", "out", "expected"),
    [
        ("claude-sonnet-4-6", 10_000, 2_000, 0.06),
        ("claude-opus-4-7", 1_000, 1_000, 0.03),
        ("gpt-4o-mini", 1_000_000, 1_000_000, 0.75),
        ("gpt-4o", 0, 0, 0.0),
    ],
)
def test_custo_estimado_pelos_tokens(model: str, inp: int, out: int, expected: float) -> None:
    assert estimate_cost(model, inp, out) == pytest.approx(expected)


def test_custo_do_provedor_zero_nao_vira_estimativa() -> None:
    # zero informado é zero (cache, cortesia), não ausência de custo
    assert cost_or_estimate(0.0, "claude-sonnet-4-6", 10_000, 10_000) == 0.0


def _config(limit: float | None, alert: int = 80, stop: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        budget_monthly_usd=Decimal(str(limit)) if limit is not None else None,
        budget_alert_percent=alert,
        budget_hard_stop=stop,
    )


@pytest.mark.parametrize(
    ("limit", "alert", "spent", "level"),
    [
        (None, 80, 50.0, None),
        (10.0, 80, 0.0, "ok"),
        (10.0, 80, 7.99, "ok"),
        (10.0, 80, 8.0, "warning"),
        (10.0, 80, 9.99, "warning"),
        (10.0, 80, 10.0, "exceeded"),
        (10.0, 80, 25.0, "exceeded"),
        (10.0, 50, 5.0, "warning"),
    ],
)
def test_nivel_do_orcamento(
    limit: float | None, alert: int, spent: float, level: str | None
) -> None:
    assert budget.state_for(_config(limit, alert), spent).level == level  # type: ignore[arg-type]


def test_so_barra_com_limite_e_bloqueio_ligado() -> None:
    assert budget.hard_limit(_config(10.0, stop=True)) == 10.0  # type: ignore[arg-type]
    assert budget.hard_limit(_config(10.0, stop=False)) is None  # type: ignore[arg-type]
    assert budget.hard_limit(_config(None, stop=True)) is None  # type: ignore[arg-type]


@pytest.mark.parametrize(("spent", "blocked"), [(9.99, False), (10.0, True), (12.0, True)])
def test_hook_barra_no_limite_com_o_motivo(
    monkeypatch: pytest.MonkeyPatch, spent: float, blocked: bool
) -> None:
    monkeypatch.setattr(budget, "cached_spend", lambda _config_id: spent)
    log = BlockLog()
    hook = budget.BudgetGuardrail(uuid4(), 10.0, log)
    run_input = RunInput(input_content="oi")
    if not blocked:
        hook.check(run_input)
        assert log.last is None
        return
    with pytest.raises(InputCheckError) as exc:
        hook.check(run_input)
    assert exc.value.message == budget.BUDGET_MESSAGE
    assert log.last is not None and log.last.rule == budget.RULE_BUDGET
    assert log.last.detail == {"spent_usd": spent, "limit_usd": 10.0}


@pytest.mark.parametrize(
    ("runs", "errors", "spike"),
    [
        (4, 4, False),  # pouco movimento não é pico
        (5, 2, False),
        (5, 3, True),
        (10, 5, True),
        (10, 4, False),
        (200, 100, True),
    ],
)
def test_pico_de_erro(runs: int, errors: int, spike: bool) -> None:
    assert alerts.is_spike(runs, errors) is spike


def test_texto_do_aviso_em_reais_de_dolar() -> None:
    config = SimpleNamespace(name="atendimento")
    state = budget.BudgetState(
        limit_usd=1250.0,
        spent_usd=1312.5,
        alert_percent=80,
        hard_stop=True,
        percent=105.0,
        level="exceeded",
    )
    text = alerts._budget_text(alerts.BUDGET_EXCEEDED, config, state)  # type: ignore[arg-type]
    assert "US$ 1.312,50 de US$ 1.250,00" in text
    assert "barrados" in text
