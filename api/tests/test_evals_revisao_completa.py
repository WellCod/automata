"""Evals da revisão humana completa (ADR-0028).

Sem banco e sem rede: rodam em todo PR. Errar a decisão grava no registro o contrário do
que o revisor fez; errar o laço deixa a volta seguir sem a pausa ou pausa onde o Agno
não sabe retomar; errar o evento de pausa deixa o run do modo teste sem pendência.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from agno.workflow.types import OnReject, OnTimeout
from pydantic import ValidationError

from app.agents.reviews import REVIEW_TEXT_CHARS, review_entries
from app.agents.tracking import _WORKFLOW_END_EVENTS, pending_steps
from app.agents.workflow_factory import loop_review_for
from app.schemas.workflow import LoopNode, LoopReview, WorkflowSettings

AGENT = "6f1c3c3e-2b7a-4bf0-9f5e-0d6a1f0c2a11"


def _step(name: str = "rascunho") -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": AGENT}


def _loop(steps: list[dict[str, Any]], review: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"type": "loop", "name": "voltas", "steps": steps, "review": review}


def _req(**over: Any) -> dict[str, Any]:
    base = {
        "step_id": "s1",
        "step_name": "analise",
        "step_type": "Step",
        "confirmed": True,
        "step_output": {"content": "valor R$ 120"},
    }
    return {**base, **over}


# --- registro: cada decisão do revisor vira a entrada certa ---


@pytest.mark.parametrize(
    ("req", "decision"),
    [
        (_req(), "approved"),
        (_req(confirmed=False), "rejected"),
        (_req(edited_output="valor R$ 210"), "edited"),
        # edição numa recusa não vale: o Agno só aplica a edição ao aprovar
        (_req(confirmed=False, edited_output="valor R$ 210"), "rejected"),
        (_req(step_type="Loop"), "loop_done"),
        (_req(step_type="Loop", confirmed=False), "loop_again"),
    ],
)
def test_decisao_do_revisor_no_registro(req: dict[str, Any], decision: str) -> None:
    [entry] = review_entries([req], {"s1"}, "ana")
    assert entry["decision"] == decision
    assert entry["by"] == "ana"


def test_sem_decisao_ou_fora_da_pausa_nao_entra() -> None:
    assert review_entries([_req(confirmed=None)], {"s1"}, "ana") == []
    # requisito que não estava pendente no run: a chamada repetida não duplica
    assert review_entries([_req()], set(), "ana") == []
    # só o último é o ativo; os anteriores voltam na lista já decididos
    old = _req(confirmed=False, rejection_feedback="faltou o valor")
    [entry] = review_entries([old, _req()], {"s1"}, None)
    assert entry["decision"] == "approved" and "feedback" not in entry
    assert entry["by"] == "desconhecido"


def test_edicao_do_criterio_de_aceite_guarda_antes_e_depois() -> None:
    [entry] = review_entries([_req(edited_output="valor R$ 210")], {"s1"}, "ana")
    assert (entry["before"], entry["after"]) == ("valor R$ 120", "valor R$ 210")


def test_dado_pessoal_mascarado_e_texto_limitado() -> None:
    big = "CPF 529.982.247-25 " + "x" * (REVIEW_TEXT_CHARS + 10)
    [entry] = review_entries(
        [_req(confirmed=False, rejection_feedback="cliente 529.982.247-25")], {"s1"}, "ana"
    )
    assert "529.982.247-25" not in entry["feedback"]
    [edited] = review_entries([_req(edited_output=big)], {"s1"}, "ana")
    assert "529.982.247-25" not in edited["after"]
    assert len(edited["after"]) == REVIEW_TEXT_CHARS


# --- laço com revisão por volta ---


def test_revisao_da_volta_vira_o_human_review_do_agno() -> None:
    node = LoopNode.model_validate(
        _loop([_step()], {"message": "  ficou bom?  ", "timeout_hours": 2})
    )
    hr = loop_review_for(node)
    assert hr is not None
    assert hr.requires_iteration_review is True
    assert hr.iteration_review_message == "ficou bom?"
    # recusar sempre pede outra volta; prazo vencido cancela
    assert hr.on_reject == OnReject.retry
    assert (hr.timeout, hr.on_timeout) == (7200, OnTimeout.cancel)
    assert loop_review_for(LoopNode.model_validate(_loop([_step()]))) is None
    blank = loop_review_for(LoopNode.model_validate(_loop([_step()], {"message": " "})))
    assert blank is not None and blank.iteration_review_message is None


def test_limites_da_revisao_da_volta() -> None:
    with pytest.raises(ValidationError):
        LoopReview(message="x" * 301)
    with pytest.raises(ValidationError):
        LoopReview(timeout_hours=169)


@pytest.mark.parametrize(
    ("steps", "problem"),
    [
        ([_loop([_step()], {})], None),
        ([_loop([_step("a"), _step("b")])], None),
        # a retomada do Agno 3.1.8 supõe uma etapa por volta
        ([_loop([_step("a"), _step("b")], {})], "uma etapa só"),
        (
            [
                _loop(
                    [{"type": "parallel", "name": "p", "branches": [_step("a"), _step("b")]}],
                    {},
                )
            ],
            "uma etapa só",
        ),
        (
            [
                {
                    "type": "condition",
                    "name": "se",
                    "rule": {"kind": "always"},
                    "steps": [_loop([_step()], {})],
                }
            ],
            "nível principal",
        ),
    ],
)
def test_revisao_da_volta_so_no_nivel_principal_e_com_uma_etapa(
    steps: list[dict[str, Any]], problem: str | None
) -> None:
    if problem is None:
        WorkflowSettings.model_validate({"steps": steps})
    else:
        with pytest.raises(ValidationError, match=problem):
            WorkflowSettings.model_validate({"steps": steps})


def test_pausa_da_volta_aparece_como_loop_com_a_saida() -> None:
    req = SimpleNamespace(
        step_id="l1",
        step_name="voltas",
        step_type="Loop",
        is_resolved=False,
        requires_output_review=True,
        output_review_message="ficou bom?",
        confirmation_message=None,
        step_output=SimpleNamespace(content="rascunho 1"),
        timeout_at=None,
        retry_count=0,
    )
    [summary] = pending_steps([req])  # type: ignore[misc]
    assert (summary["when"], summary["output"]) == ("loop", "rascunho 1")
    assert summary["message"] == "ficou bom?"


# --- modo teste: o run em stream fica pausado ---


@pytest.mark.parametrize("event", ["StepOutputReview", "StepPaused", "WorkflowPaused"])
def test_pausa_no_stream_marca_o_run_como_pausado(event: str) -> None:
    # no stream em primeiro plano o WorkflowPaused vem da rota, fora do gerador
    assert _WORKFLOW_END_EVENTS[event] == "paused"
