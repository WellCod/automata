"""Evals do roteador, da entrada por etapa e da suíte por etapa (ADR-0038).

Sem banco e sem LLM. Errar o roteador manda o cliente de troca para a cobrança; errar a
entrada da etapa faz a revisão julgar o rascunho sem ver a pergunta; errar a checagem
por etapa aprova uma triagem que classificou errado.
"""

from typing import Any

import pytest
from agno.workflow import StepInput, StepOutput

from app.agents.workflow_factory import render_input, router_selector
from app.evals.runner import TextScorer
from app.schemas.eval import EvalCaseInput, TextCheck, kind_problem
from app.schemas.workflow import WorkflowRule

ROUTES = [
    (WorkflowRule(kind="contains", source="input", value="troca"), "troca"),
    (WorkflowRule(kind="contains", source="input", value="reembolso"), "reembolso"),
    (WorkflowRule(kind="starts_with", source="previous", value="urgente"), "prioridade"),
]


def _input(message: str, previous: str | None = None) -> StepInput:
    outputs = {"triagem": StepOutput(step_name="triagem", content=previous)} if previous else None
    return StepInput(input=message, previous_step_content=previous, previous_step_outputs=outputs)


@pytest.mark.parametrize(
    ("message", "previous", "expected"),
    [
        ("Quero TROCAR o tênis", None, "troca"),
        ("troca ou reembolso?", None, "troca"),  # a ordem dos caminhos decide
        ("só o reembolso", None, "reembolso"),
        ("oi", "Urgente: cliente irritado", "prioridade"),
        ("oi", "tudo certo", "padrao"),
        ("", None, "padrao"),
    ],
)
def test_roteador_pela_regra_e_pela_ordem(
    message: str, previous: str | None, expected: str
) -> None:
    assert router_selector(ROUTES, "padrao")(_input(message, previous)) == expected


def test_sem_padrao_nada_roda() -> None:
    assert router_selector(ROUTES, None)(_input("qual o horário?")) == []


def _outputs() -> dict[str, StepOutput]:
    paralelo = StepOutput(
        step_name="analise",
        content="resumo do paralelo",
        steps=[
            StepOutput(step_name="tecnica", content="parecer técnico"),
            StepOutput(step_name="financeira", content="parecer financeiro"),
        ],
    )
    return {"triagem": StepOutput(step_name="triagem", content="troca"), "analise": paralelo}


@pytest.mark.parametrize(
    ("mode", "template", "expected"),
    [
        ("original", None, "pergunta do cliente"),
        ("template", "{entrada}", "pergunta do cliente"),
        # anterior é a saída mais funda da última etapa, não a frase-resumo do contêiner
        ("template", "{anterior}", "parecer financeiro"),
        ("template", "T={etapa:triagem} F={etapa:tecnica}", "T=troca F=parecer técnico"),
        ("template", "[{etapa:fantasma}]", "[]"),
        ("template", "{entrada}|{anterior}", "pergunta do cliente|parecer financeiro"),
    ],
)
def test_entrada_da_etapa(mode: str, template: str | None, expected: str) -> None:
    assert render_input(mode, template, "pergunta do cliente", _outputs()) == expected


def test_texto_sem_etapa_anterior() -> None:
    assert render_input("template", "{entrada} / {anterior}", "oi", None) == "oi / "


def _scorer(*checks: TextCheck) -> TextScorer:
    return TextScorer(list(checks))


@pytest.mark.parametrize(
    ("contents", "passed"),
    [
        ({"triagem": "categoria: troca"}, True),
        ({"triagem": "categoria: cobrança"}, False),
        ({}, False),  # a etapa não rodou
    ],
)
def test_checagem_numa_etapa(contents: dict[str, str], passed: bool) -> None:
    check = TextCheck(kind="contains", value="troca", step="triagem")
    [verdict] = _scorer(check).verdicts("resposta final sem a palavra", contents)
    assert verdict["passed"] is passed and verdict["step"] == "triagem"


def test_sem_etapa_olha_a_resposta_final() -> None:
    [verdict] = _scorer(TextCheck(kind="contains", value="troca")).verdicts(
        "aprovada a troca", {"triagem": "x"}
    )
    assert verdict["passed"] is True and "step" not in verdict


def _case(**extra: Any) -> EvalCaseInput:
    return EvalCaseInput.model_validate(
        {"name": "c", "input": "oi", "checks": [{"type": "text", "kind": "not_empty"}], **extra}
    )


@pytest.mark.parametrize(
    ("kind", "case", "history", "names", "problem"),
    [
        ("workflow", _case(context=["antes"]), 0, None, "histórico"),
        ("workflow", _case(context=["antes"]), 2, None, None),
        (
            "agent",
            _case(checks=[{"type": "text", "kind": "not_empty", "step": "triagem"}]),
            0,
            None,
            "só vale para workflow",
        ),
        (
            "workflow",
            _case(checks=[{"type": "text", "kind": "not_empty", "step": "fantasma"}]),
            0,
            {"triagem"},
            "fantasma",
        ),
        (
            "workflow",
            _case(checks=[{"type": "text", "kind": "not_empty", "step": "triagem"}]),
            0,
            {"triagem"},
            None,
        ),
    ],
)
def test_regras_do_caso(
    kind: str, case: EvalCaseInput, history: int, names: set[str] | None, problem: str | None
) -> None:
    found = kind_problem(kind, case, history, names)
    if problem is None:
        assert found is None
    else:
        assert found is not None and problem in found
