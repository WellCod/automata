"""Evals da revisão humana no workflow (ADR-0023).

Sem banco e sem rede: rodam em todo PR. Errar o mapeamento deixa a etapa rodar
sem a aprovação que devia esperar; errar o resumo mostra ao revisor a saída
errada ou nenhuma.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from agno.workflow.types import OnReject, OnTimeout
from pydantic import ValidationError

from app.agents.tracking import PENDING_OUTPUT_CHARS, pending_steps
from app.agents.workflow_factory import REVIEW_RETRIES, human_review_for
from app.schemas.workflow import StepNode, StepReview, WorkflowSettings

AGENT = "6f1c3c3e-2b7a-4bf0-9f5e-0d6a1f0c2a11"


def _step(name: str = "analise", **extra: Any) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": AGENT, **extra}


@pytest.mark.parametrize(
    ("review", "confirm", "output_review", "on_reject", "timeout"),
    [
        (None, False, False, OnReject.skip, None),
        ({"when": "before"}, True, False, OnReject.cancel, None),
        ({"when": "after", "on_reject": "retry"}, False, True, OnReject.retry, None),
        (
            {"when": "after", "on_reject": "skip", "timeout_hours": 24},
            False,
            True,
            OnReject.skip,
            86400,
        ),
    ],
)
def test_revisao_vira_o_human_review_do_agno(
    review: dict[str, Any] | None,
    confirm: bool,
    output_review: bool,
    on_reject: OnReject,
    timeout: int | None,
) -> None:
    hr = human_review_for(StepNode.model_validate(_step(review=review)))
    assert hr.requires_confirmation is confirm
    assert bool(hr.requires_output_review) is output_review
    assert hr.timeout == timeout
    if review is not None:
        # sem revisão vale o padrão do Agno; com ela, a recusa é a escolhida
        assert hr.on_reject == on_reject
        assert hr.on_timeout == OnTimeout.cancel
        assert hr.max_retries == REVIEW_RETRIES


def test_mensagem_vai_para_o_campo_do_momento_da_revisao() -> None:
    before = human_review_for(
        StepNode.model_validate(_step(review={"when": "before", "message": "libera?"}))
    )
    after = human_review_for(
        StepNode.model_validate(_step(review={"when": "after", "message": "confere"}))
    )
    assert (before.confirmation_message, before.output_review_message) == ("libera?", None)
    assert (after.confirmation_message, after.output_review_message) == (None, "confere")


def test_refazer_so_na_revisao_da_saida() -> None:
    with pytest.raises(ValidationError, match="revisão da saída"):
        StepReview(when="before", on_reject="retry")
    with pytest.raises(ValidationError):
        StepReview(when="after", timeout_hours=200)


@pytest.mark.parametrize(
    ("steps", "ok"),
    [
        ([_step(review={"when": "after"})], True),
        (
            [
                {
                    "type": "condition",
                    "name": "se",
                    "rule": {"kind": "always"},
                    "steps": [_step("dentro", review={"when": "before"})],
                },
            ],
            True,
        ),
        (
            [
                {
                    "type": "parallel",
                    "name": "ramos",
                    "branches": [_step("a", review={"when": "after"}), _step("b")],
                },
                _step("fim"),
            ],
            False,
        ),
        (
            [
                {
                    "type": "loop",
                    "name": "voltas",
                    "steps": [
                        {
                            "type": "condition",
                            "name": "se",
                            "rule": {"kind": "always"},
                            "steps": [_step("fundo", review={"when": "after"})],
                        }
                    ],
                }
            ],
            False,
        ),
    ],
)
def test_revisao_fora_de_paralelo_e_de_laco(steps: list[dict[str, Any]], ok: bool) -> None:
    if ok:
        WorkflowSettings.model_validate({"steps": steps})
    else:
        with pytest.raises(ValidationError, match="fora de paralelo e de laço"):
            WorkflowSettings.model_validate({"steps": steps})


def _req(**over: Any) -> SimpleNamespace:
    base = {
        "step_id": "s1",
        "step_name": "analise",
        "is_resolved": False,
        "requires_output_review": True,
        "output_review_message": "confere o valor",
        "confirmation_message": None,
        "step_output": SimpleNamespace(content="R$ 120"),
        "timeout_at": None,
        "retry_count": 0,
    }
    return SimpleNamespace(**{**base, **over})


def test_resumo_so_do_pendente_com_a_saida_cortada() -> None:
    assert pending_steps(None) is None
    assert pending_steps([_req(is_resolved=True)]) is None
    long = "x" * (PENDING_OUTPUT_CHARS + 50)
    [summary] = pending_steps(
        [_req(is_resolved=True, step_id="velho"), _req(step_output=SimpleNamespace(content=long))]
    )  # type: ignore[list-item]
    assert summary["step_id"] == "s1" and summary["when"] == "after"
    assert len(summary["output"]) == PENDING_OUTPUT_CHARS
    assert summary["message"] == "confere o valor"


def test_confirmacao_antes_nao_mostra_saida() -> None:
    [summary] = pending_steps(  # type: ignore[misc]
        [_req(requires_output_review=False, confirmation_message="libera?")]
    )
    assert summary["when"] == "before"
    assert summary["output"] is None and summary["message"] == "libera?"
