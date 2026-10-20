"""Evals das regras e da estrutura de workflow (ADR-0014).

Sem LLM: regra e validação são código nosso, então rodam em todo PR. Os textos
são respostas reais de triagem e mensagens de cliente. Os casos marcados como
limite documentam o que a regra por texto não resolve (negação, acento): mudar
o comportamento deles é decisão, não correção silenciosa.
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from agno.workflow import StepInput, StepOutput
from pydantic import ValidationError

from app.agents.workflow_factory import condition_evaluator, loop_end_condition, rule_matches
from app.schemas.workflow import WorkflowRule, WorkflowSettings


@dataclass(frozen=True)
class RuleCase:
    kind: str
    value: str
    text: str
    expected: bool


TRIAGEM = (
    "Classificação: REEMBOLSO\nPrioridade: alta\nResumo: cliente cobrado duas vezes no pedido 4471."
)

RULE_CASES: list[RuleCase] = [
    # contém, sem diferenciar maiúsculas e com espaços em volta do valor
    RuleCase("contains", "reembolso", "Quero o REEMBOLSO do pedido 4471", True),
    RuleCase("contains", " Reembolso ", TRIAGEM, True),
    RuleCase("contains", "reembolso", "Quero trocar o tamanho da camiseta", False),
    RuleCase("contains", "prioridade: alta", TRIAGEM, True),
    RuleCase("contains", "estorno", "Cadê o ESTORNO da minha compra?", True),
    # limite: substring não entende negação nem flexão sem acento
    RuleCase("contains", "reembolso", "Não quero reembolso, só a troca", True),
    RuleCase("contains", "reembolso", "Quero ser reembolsado", False),
    RuleCase("contains", "cancelamento", "cancelamênto do plano", False),
    # não contém
    RuleCase("not_contains", "urgente", "Dúvida sobre a fatura", True),
    RuleCase("not_contains", "urgente", "URGENTE: sistema fora do ar", False),
    # começa com: ignora espaço e quebra de linha no início
    RuleCase("starts_with", "classificação: reembolso", TRIAGEM, True),
    RuleCase("starts_with", "urgente", "\n  Urgente: pagar hoje", True),
    RuleCase("starts_with", "urgente", "Não é urgente", False),
    # vazio e não vazio: só espaço conta como vazio
    RuleCase("empty", "", "   \n\t", True),
    RuleCase("empty", "", "ok", False),
    RuleCase("not_empty", "", ".", True),
    RuleCase("not_empty", "", "", False),
    RuleCase("always", "", "", True),
]


@pytest.mark.parametrize("case", RULE_CASES, ids=lambda c: f"{c.kind}:{c.text[:30]}")
def test_regra(case: RuleCase) -> None:
    rule = WorkflowRule(kind=case.kind, value=case.value)  # type: ignore[arg-type]
    assert rule_matches(rule, case.text) is case.expected


def _parallel_output() -> StepOutput:
    return StepOutput(
        step_name="análises",
        # o Agno resume o contêiner numa frase; a regra precisa ler a resposta do ramo
        content="Parallel step análises completed with 2 results",
        steps=[
            StepOutput(step_name="técnica", content="sem falha no sistema"),
            StepOutput(step_name="financeira", content="cobrança duplicada: reembolso devido"),
        ],
    )


def test_condicao_le_a_resposta_da_etapa_e_nao_o_resumo_do_paralelo() -> None:
    step_input = StepInput(
        input="oi, fui cobrado duas vezes",
        previous_step_content="Parallel step análises completed with 2 results",
        previous_step_outputs={
            "triagem": StepOutput(step_name="triagem", content=TRIAGEM),
            "análises": _parallel_output(),
        },
    )
    previous = condition_evaluator(WorkflowRule(kind="contains", value="reembolso devido"))
    assert previous(step_input) is True
    # o resumo do Agno nunca deveria casar regra de negócio
    resumo = condition_evaluator(WorkflowRule(kind="contains", value="completed"))
    assert resumo(step_input) is False
    # source=input ignora as etapas
    entrada = condition_evaluator(WorkflowRule(kind="contains", value="cobrado", source="input"))
    assert entrada(step_input) is True


def test_loop_para_pela_ultima_etapa_da_volta() -> None:
    done = loop_end_condition(WorkflowRule(kind="contains", value="aprovado"))
    assert done([]) is False
    volta = [
        StepOutput(step_name="redige", content="rascunho v2"),
        StepOutput(step_name="revisa", content="APROVADO, pode enviar"),
    ]
    assert done(volta) is True
    assert done(list(reversed(volta))) is False


def _step(name: str, **extra: Any) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": str(uuid4()), **extra}


# critério de aceite da fase: triagem, paralelo, consolidação e condição de reembolso
ATENDIMENTO = [
    _step("triagem"),
    {"type": "parallel", "name": "análises", "branches": [_step("técnica"), _step("financeira")]},
    _step("consolidação"),
    {
        "type": "condition",
        "name": "se reembolso",
        "rule": {"kind": "contains", "source": "input", "value": "reembolso"},
        "steps": [_step("revisão")],
    },
]


def _nest(depth: int) -> dict[str, Any]:
    node: dict[str, Any] = _step(f"folha-{depth}")
    for level in range(depth - 1, 0, -1):
        node = {"type": "loop", "name": f"loop-{level}", "steps": [node]}
    return node


STRUCTURE_CASES: list[tuple[str, list[dict[str, Any]], str | None]] = [
    ("atendimento completo", ATENDIMENTO, None),
    ("três níveis cabem", [_nest(3)], None),
    ("quatro níveis não", [_nest(4)], "aninhamento"),
    ("termina em paralelo", ATENDIMENTO[:2], "terminar num paralelo"),
    ("nome repetido", [_step("a"), _step("a")], "repetidos"),
    ("trinta etapas cabem", [_step(f"e{i}") for i in range(30)], None),
    ("trinta e uma não", [_step(f"e{i}") for i in range(31)], "30 etapas"),
    (
        "paralelo com um ramo",
        [{"type": "parallel", "name": "p", "branches": [_step("x")]}, _step("y")],
        "branches",
    ),
    (
        "etapa sem executor",
        [{"type": "step", "name": "sem quem"}],
        "agente ou de um time",
    ),
    (
        "regra sem texto",
        [
            {
                "type": "condition",
                "name": "c",
                "rule": {"kind": "contains", "value": "  "},
                "steps": [_step("x")],
            }
        ],
        "precisa de um texto",
    ),
    (
        "repetição acima do limite",
        [{"type": "loop", "name": "l", "steps": [_step("x")], "max_iterations": 11}],
        "max_iterations",
    ),
]


@pytest.mark.parametrize(
    ("steps", "error"),
    [(steps, error) for _, steps, error in STRUCTURE_CASES],
    ids=[name for name, _, _ in STRUCTURE_CASES],
)
def test_estrutura(steps: list[dict[str, Any]], error: str | None) -> None:
    if error is None:
        WorkflowSettings.model_validate({"steps": steps})
        return
    with pytest.raises(ValidationError, match=error):
        WorkflowSettings.model_validate({"steps": steps})
