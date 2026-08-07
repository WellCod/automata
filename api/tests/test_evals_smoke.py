"""Suite smoke de confiabilidade — sem chamada real de LLM.

Testa a lógica do ReliabilityEval usando RunOutput construído manualmente,
verificando que os critérios de aprovação/reprovação estão definidos
corretamente para as tool calls esperadas nos agentes do automata.

Por convenção: fixtures gravadas substituem o LLM. A chamada real fica
reservada para a suite noturna (test_evals_nightly.py).
"""

from agno.eval.reliability import ReliabilityEval, ReliabilityResult
from agno.models.response import ToolExecution
from agno.run.agent import RunOutput


def _run_output(*tool_names: str, error: bool = False) -> RunOutput:
    """Constrói um RunOutput com execuções limpas (ou com erro) das tools indicadas."""
    return RunOutput(
        tools=[
            ToolExecution(tool_name=name, tool_call_error=True if error else None)
            for name in tool_names
        ]
    )


def _eval(
    output: RunOutput,
    expected: list[str],
    *,
    allow_additional: bool = False,
    expected_args: dict | None = None,
) -> ReliabilityResult:
    return ReliabilityEval(
        agent_response=output,
        expected_tool_calls=expected,
        allow_additional_tool_calls=allow_additional,
        expected_tool_call_arguments=expected_args,
        show_spinner=False,
        telemetry=False,
    )._evaluate()


# ---------------------------------------------------------------------------
# Cenários de aprovação
# ---------------------------------------------------------------------------


def test_tool_chamada_corretamente_passa() -> None:
    result = _eval(_run_output("get_weather"), ["get_weather"])
    assert result.eval_status == "PASSED"
    assert "get_weather" in result.passed_tool_calls
    assert result.failed_tool_calls == []
    assert result.missing_tool_calls == []


def test_multiplas_tools_todas_chamadas_passa() -> None:
    result = _eval(
        _run_output("search_web", "summarize"),
        ["search_web", "summarize"],
    )
    assert result.eval_status == "PASSED"
    assert set(result.passed_tool_calls) == {"search_web", "summarize"}


def test_tool_extra_com_allow_additional_passa() -> None:
    result = _eval(
        _run_output("expected_tool", "bonus_tool"),
        ["expected_tool"],
        allow_additional=True,
    )
    assert result.eval_status == "PASSED"
    assert "bonus_tool" in result.additional_tool_calls


def test_argumentos_corretos_passam() -> None:
    output = RunOutput(tools=[ToolExecution(tool_name="add", tool_args={"a": 2, "b": 3})])
    result = _eval(output, ["add"], expected_args={"add": {"a": 2, "b": 3}})
    assert result.eval_status == "PASSED"
    assert "add" in result.passed_argument_checks


# ---------------------------------------------------------------------------
# Cenários de reprovação
# ---------------------------------------------------------------------------


def test_tool_esperada_nao_chamada_reprova() -> None:
    result = _eval(_run_output(), ["get_weather"])
    assert result.eval_status == "FAILED"
    assert "get_weather" in result.missing_tool_calls


def test_tool_inesperada_em_modo_estrito_reprova() -> None:
    result = _eval(_run_output("unexpected_tool"), ["expected_tool"])
    assert result.eval_status == "FAILED"
    assert "unexpected_tool" in result.failed_tool_calls


def test_argumentos_errados_reprovam() -> None:
    output = RunOutput(tools=[ToolExecution(tool_name="multiply", tool_args={"a": 1, "b": 1})])
    result = _eval(output, ["multiply"], expected_args={"multiply": {"a": 10, "b": 5}})
    assert result.eval_status == "FAILED"
    assert "multiply" in result.failed_argument_checks


def test_execucao_com_erro_nao_satisfaz_expectativa() -> None:
    """Tool chamada mas com erro não conta como execução limpa — ADR-0008."""
    result = _eval(_run_output("get_weather", error=True), ["get_weather"])
    assert result.eval_status == "FAILED"
    # Agno 2.8.0 anota entries de tentativas com erro: verifica apenas que
    # a tool aparece como ausente (com ou sem anotação).
    assert any("get_weather" in entry for entry in result.missing_tool_calls)


# ---------------------------------------------------------------------------
# assert_passed helper
# ---------------------------------------------------------------------------


def test_assert_passed_nao_levanta_quando_passou() -> None:
    result = _eval(_run_output("my_tool"), ["my_tool"])
    result.assert_passed()  # não deve levantar


def test_assert_passed_levanta_quando_falhou() -> None:
    import pytest

    result = _eval(_run_output(), ["my_tool"])
    with pytest.raises(AssertionError, match="ReliabilityEval failed"):
        result.assert_passed()
