"""Evals da suíte de workflow e do caso que espera bloqueio (ADR-0022).

Sem banco e sem rede: rodam em todo PR. Errar o caminho do workflow aprova um
fluxo que mudou de rota; errar o bloqueio aprova guardrail que deixou passar.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from agno.run.workflow import WorkflowRunOutput
from agno.workflow import StepOutput

from app.evals.runner import PlannedCase, _blocked_result, steps_verdict
from app.evals.workflow_case import steps_run
from app.guardrails.input import Block, BlockLog
from app.schemas.eval import EvalCaseInput, StepsCheck, kind_problem


def _spec(checks: list[dict[str, Any]], **extra: Any) -> EvalCaseInput:
    return EvalCaseInput.model_validate({"name": "c", "input": "oi", "checks": checks, **extra})


@pytest.mark.parametrize(
    ("kind", "checks", "context", "problem"),
    [
        ("agent", [{"type": "text", "kind": "not_empty"}], [], None),
        ("agent", [{"type": "blocked"}], [], None),
        ("agent", [{"type": "steps", "steps": ["a"]}], [], "steps"),
        ("team", [{"type": "steps", "steps": ["a"]}], [], "steps"),
        ("workflow", [{"type": "steps", "steps": ["a"]}], [], None),
        ("workflow", [{"type": "tools", "tools": ["x"]}], [], "tools"),
        ("workflow", [{"type": "blocked"}], [], "blocked"),
        ("workflow", [{"type": "text", "kind": "not_empty"}], ["antes"], "turnos anteriores"),
    ],
)
def test_checagens_por_tipo_de_config(
    kind: str, checks: list[dict[str, Any]], context: list[str], problem: str | None
) -> None:
    found = kind_problem(kind, _spec(checks, context=context))
    if problem is None:
        assert found is None
    else:
        assert found is not None and problem in found


def test_bloqueio_nao_combina_com_outra_checagem() -> None:
    with pytest.raises(ValueError, match="não leva outras checagens"):
        _spec([{"type": "blocked"}, {"type": "text", "kind": "not_empty"}])


def _out(name: str, steps: list[StepOutput] | None = None) -> StepOutput:
    return StepOutput(step_name=name, content=name, steps=steps)


def test_etapas_que_rodaram_sem_os_conteineres() -> None:
    output = WorkflowRunOutput(
        step_results=[
            _out("triagem"),
            _out("análises", [_out("técnica"), _out("financeira")]),
            # laço: uma lista por volta
            [_out("consolida"), _out("consolida")],
            _out("se reembolso", [_out("revisão")]),
        ]
    )
    known = {"triagem", "técnica", "financeira", "consolida", "revisão"}
    assert steps_run(output, known) == [
        "triagem",
        "técnica",
        "financeira",
        "consolida",
        "consolida",
        "revisão",
    ]


@pytest.mark.parametrize(
    ("expected", "exclusive", "ran", "passed", "missing", "extra"),
    [
        (["a", "b"], False, ["a", "b", "c"], True, [], []),
        (["a", "b"], True, ["a", "b", "c"], False, [], ["c"]),
        (["a", "b"], False, ["a"], False, ["b"], []),
        # condição que não entrou: a etapa de dentro não rodou
        (["revisão"], False, [], False, ["revisão"], []),
        # laço repete a etapa: conta uma vez
        (["a"], True, ["a", "a"], True, [], []),
    ],
)
def test_veredito_das_etapas(
    expected: list[str],
    exclusive: bool,
    ran: list[str],
    passed: bool,
    missing: list[str],
    extra: list[str],
) -> None:
    verdict = steps_verdict(StepsCheck(steps=expected, exclusive=exclusive), ran)
    assert (verdict["passed"], verdict["missing"], verdict["extra"]) == (passed, missing, extra)


def _planned(check: dict[str, Any], blocked_by: str | None) -> PlannedCase:
    log = BlockLog()
    if blocked_by is not None:
        log.blocks.append(Block(blocked_by, "barrado", {}))
    return PlannedCase(0, None, "c", _spec([check]), None, {}, log)


def _result(**over: Any) -> Any:
    base = {
        "skipped": False,
        "timed_out": False,
        "error": None,
        "score": None,
        "output": "",
        "tools_called": (),
        "duration_seconds": 0.1,
        "session_id": "s",
    }
    return SimpleNamespace(**{**base, **over})


@pytest.mark.parametrize(
    ("rule", "blocked_by", "result", "status"),
    [
        (None, "off_topic", _result(error="agent: barrado"), "passed"),
        ("off_topic", "off_topic", _result(error="agent: barrado"), "passed"),
        ("pii_detected", "off_topic", _result(error="agent: barrado"), "failed"),
        # respondeu: o scorer reprovou
        (None, None, _result(score=SimpleNamespace(passed=False)), "failed"),
        # orçamento barrou: não é o guardrail que o caso testa
        (None, "budget_exceeded", _result(error="agent: barrado"), "error"),
        # caiu sem bloquear e sem responder
        (None, None, _result(error="agent: falha do modelo"), "error"),
        (None, None, _result(timed_out=True), "error"),
    ],
)
def test_veredito_do_bloqueio(
    rule: str | None, blocked_by: str | None, result: Any, status: str
) -> None:
    check = {"type": "blocked", "rule": rule}
    planned = _planned(check, blocked_by)
    row = _blocked_result(planned, planned.spec.checks[0], result)  # type: ignore[arg-type]
    assert row.status == status
