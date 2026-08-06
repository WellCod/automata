"""Suite noturna de evals de confiabilidade — requer LLM real.

Só roda quando o pytest marker `nightly` é selecionado explicitamente
(via `-m nightly`). O workflow .github/workflows/evals-nightly.yml
dispara esta suite com as credenciais de CI.

Nunca rodar estes testes em PR — chamam LLM de verdade e têm custo.
"""

import os

import pytest
from agno.agent import Agent
from agno.eval.reliability import ReliabilityEval
from agno.tools import tool

pytestmark = pytest.mark.nightly


def _anthropic_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY não definida — pulando eval noturno")
    return key


# ---------------------------------------------------------------------------
# Ferramenta determinística para os evals
# ---------------------------------------------------------------------------


@tool
def calcular_soma(a: int, b: int) -> int:
    """Soma dois inteiros e retorna o resultado."""
    return a + b


@tool
def consultar_cambio(moeda_origem: str, moeda_destino: str) -> float:
    """Consulta taxa de câmbio entre duas moedas. Retorna taxa fictícia para evals."""
    _ = moeda_origem, moeda_destino
    return 5.72


# ---------------------------------------------------------------------------
# Evals com Claude Haiku (modelo mais barato para CI noturno)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def agente_calculadora() -> Agent:
    _anthropic_key()
    from agno.models.anthropic import Claude

    return Agent(
        model=Claude(id="claude-haiku-4-5"),
        tools=[calcular_soma],
        show_tool_calls=False,
    )


@pytest.fixture(scope="module")
def agente_cambio() -> Agent:
    _anthropic_key()
    from agno.models.anthropic import Claude

    return Agent(
        model=Claude(id="claude-haiku-4-5"),
        tools=[consultar_cambio],
        show_tool_calls=False,
    )


def test_agente_chama_calcular_soma(agente_calculadora: Agent) -> None:
    response = agente_calculadora.run("Quanto é 12 + 34?", stream=False)
    eval_ = ReliabilityEval(
        agent_response=response,
        expected_tool_calls=["calcular_soma"],
        show_spinner=False,
        telemetry=False,
    )
    result = eval_.run()
    assert result is not None
    result.assert_passed()


def test_agente_chama_soma_com_argumentos_corretos(agente_calculadora: Agent) -> None:
    response = agente_calculadora.run("Qual é a soma de 7 e 8?", stream=False)
    eval_ = ReliabilityEval(
        agent_response=response,
        expected_tool_calls=["calcular_soma"],
        expected_tool_call_arguments={"calcular_soma": {"a": 7, "b": 8}},
        show_spinner=False,
        telemetry=False,
    )
    result = eval_.run()
    assert result is not None
    result.assert_passed()


def test_agente_chama_consultar_cambio(agente_cambio: Agent) -> None:
    response = agente_cambio.run("Qual é a taxa de câmbio do USD para BRL?", stream=False)
    eval_ = ReliabilityEval(
        agent_response=response,
        expected_tool_calls=["consultar_cambio"],
        show_spinner=False,
        telemetry=False,
    )
    result = eval_.run()
    assert result is not None
    result.assert_passed()


def test_agente_nao_chama_tool_errada(agente_calculadora: Agent) -> None:
    """O agente de calculadora não deve chamar consultar_cambio."""
    response = agente_calculadora.run("Quanto é 5 + 3?", stream=False)
    eval_ = ReliabilityEval(
        agent_response=response,
        expected_tool_calls=["calcular_soma"],
        allow_additional_tool_calls=False,
        show_spinner=False,
        telemetry=False,
    )
    result = eval_.run()
    assert result is not None
    result.assert_passed()
