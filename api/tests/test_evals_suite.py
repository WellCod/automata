"""Evals da própria suíte de testes (ADR-0015): o que conta como aprovado, não avaliado e bloqueio.

Sem LLM e sem banco: roda em todo PR. Cobrem as decisões que, se mudarem em
silêncio, fazem o gate liberar o que não devia — scorer de texto sobre respostas
reais, montagem do Case do Agno (juiz só quando há modelo, nunca no modo demo),
tradução do resultado do runner e o veredito do gate.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from agno.agent import Agent
from agno.eval.suite import CaseResult, JudgeMode

from app.evals import gate, runner
from app.evals.compare import change
from app.evals.runner import JUDGE_IN_DEMO, JUDGE_WITHOUT_MODEL, TextScorer, plan_case, result_from
from app.schemas.eval import TextCheck
from tests.fake_models import FixedReplyModel

RESPOSTA = (
    "Olá! Pela nossa política, a troca pode ser pedida em até 30 dias corridos. "
    "No Pix, o reembolso cai em até 5 dias úteis."
)


@dataclass(frozen=True)
class TextCase:
    kind: str
    value: str
    text: str
    expected: bool


TEXT_CASES = [
    TextCase("contains", "30 DIAS", RESPOSTA, True),
    TextCase("contains", "reembolso", RESPOSTA, True),
    TextCase("not_contains", "garantimos", RESPOSTA, True),
    TextCase("not_contains", "pix", RESPOSTA, False),
    TextCase("starts_with", "olá", RESPOSTA, True),
    TextCase("not_empty", "", "  ok ", True),
    TextCase("empty", "", "\n ", True),
    # limite conhecido: substring não entende negação
    TextCase("contains", "reembolso", "Não temos reembolso nesse caso.", True),
]


@pytest.mark.parametrize("case", TEXT_CASES, ids=lambda c: f"{c.kind}:{c.value or '-'}")
async def test_scorer_de_texto_sobre_respostas_reais(case: TextCase) -> None:
    score = await TextScorer([TextCheck(kind=case.kind, value=case.value)]).ascore(
        SimpleNamespace(content=case.text)
    )
    assert score.passed is case.expected
    assert score.value == (1.0 if case.expected else 0.0)


async def test_scorer_exige_todas_as_regras() -> None:
    checks = [
        TextCheck(kind="contains", value="30 dias"),
        TextCheck(kind="contains", value="boleto"),
    ]
    score = await TextScorer(checks).ascore(SimpleNamespace(content=RESPOSTA))
    assert (score.passed, score.value) == (False, 0.5)
    assert score.reason == "falhou: contains 'boleto'"


@pytest.fixture
def fake_factory(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Troca as fábricas reais por um agente de resposta fixa e registra o que foi montado."""
    built: list[str] = []

    def agent_from(config_id: Any, resolved: Any, *, tracked: bool) -> Agent:
        built.append("agent")
        return Agent(model=FixedReplyModel(id="x", reply=RESPOSTA))

    monkeypatch.setattr(runner, "load_version", lambda config_id, version_id: None)
    monkeypatch.setattr(runner, "agent_from", agent_from)
    return built


def _snapshot(*checks: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(uuid4()), "name": "caso", "input": "Qual o prazo?", "checks": list(checks)}


JUDGE = {"type": "judge", "criteria": "Cita o prazo de 30 dias", "mode": "numeric", "threshold": 8}
TOOLS = {"type": "tools", "tools": ["buscar_politicas"], "allow_additional": False}
TEXT = {"type": "text", "kind": "contains", "value": "30 dias"}


def test_caso_com_tudo_vira_um_case_do_agno(fake_factory: list[str]) -> None:
    planned = plan_case(0, _snapshot(TEXT, TOOLS, JUDGE), uuid4(), "agent", uuid4(), None)
    case = planned.agno_case
    assert case is not None and fake_factory == ["agent"]
    assert case.criteria == JUDGE["criteria"]
    assert (case.judge_mode, case.judge_threshold) == (JudgeMode.NUMERIC, 8)
    assert case.expected_tool_calls == ("buscar_politicas",)
    assert case.allow_additional_tool_calls is False
    assert isinstance(case.scorer, TextScorer)
    assert planned.skipped == {}


@pytest.mark.parametrize("motivo", [JUDGE_IN_DEMO, JUDGE_WITHOUT_MODEL])
def test_juiz_indisponivel_nao_entra_no_case(fake_factory: list[str], motivo: str) -> None:
    planned = plan_case(0, _snapshot(TEXT, JUDGE), uuid4(), "agent", uuid4(), motivo)
    assert planned.agno_case is not None and planned.agno_case.criteria is None
    assert planned.skipped == {"judge": motivo}

    only_judge = plan_case(0, _snapshot(JUDGE), uuid4(), "agent", uuid4(), motivo)
    # sem checagem que rode, nem monta o agente: o caso fica não avaliado
    assert only_judge.agno_case is None and fake_factory == ["agent"]
    row = result_from(only_judge, None)
    assert row.status == "not_evaluated"
    assert row.checks[0]["passed"] is None and row.checks[0]["reason"] == motivo


def _result(**fields: Any) -> CaseResult:
    return CaseResult(name="caso", tags=(), **fields)


@pytest.mark.parametrize(
    ("fields", "status"),
    [
        ({"reliability_passed": True}, "passed"),
        ({"reliability_passed": False}, "failed"),
        ({"reliability_passed": True, "error": "agent: provedor fora do ar"}, "error"),
        ({"timed_out": True}, "error"),
        ({"skipped": True}, "not_evaluated"),
    ],
)
def test_resultado_do_runner_vira_status(
    fake_factory: list[str], fields: dict[str, Any], status: str
) -> None:
    planned = plan_case(0, _snapshot(TOOLS), uuid4(), "agent", uuid4(), None)
    row = result_from(planned, _result(**fields))
    assert row.status == status
    if fields.get("timed_out"):
        assert row.error == "tempo esgotado"


def test_gate_so_libera_suite_completa_e_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(draft_version_id=uuid4())

    def verdict(run: Any) -> gate.GateVerdict:
        monkeypatch.setattr(gate, "latest_run", lambda session, c: run)
        return gate.draft_verdict(None, config)  # type: ignore[arg-type]

    def run(**fields: Any) -> SimpleNamespace:
        return SimpleNamespace(**{"status": "completed", "total": 3, "passed": 3, **fields})

    assert verdict(run()).ok is True
    assert verdict(None).ok is False
    assert verdict(run(status="running")).ok is False
    assert verdict(run(status="failed")).ok is False
    # não avaliado não é aprovado: no modo demo, caso de juiz trava o gate
    assert verdict(run(passed=2)).reason == "1 de 3 casos não passaram no rascunho atual"
    assert verdict(run(total=0, passed=0)).ok is False
    assert gate.draft_verdict(None, SimpleNamespace(draft_version_id=None)).ok is False  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("base", "target", "expected"),
    [
        ("passed", "failed", "regression"),
        ("passed", "error", "regression"),
        ("passed", "not_evaluated", "regression"),
        ("failed", "passed", "fix"),
        ("failed", "error", "same"),
        ("passed", "passed", "same"),
        (None, "passed", "new"),
        ("passed", None, "removed"),
    ],
)
def test_comparacao(base: str | None, target: str | None, expected: str) -> None:
    assert change(base, target) == expected
