"""Padrões próprios na máscara de dados pessoais (ADR-0032)."""

import time

import pytest
from agno.exceptions import InputCheckError, OutputCheckError
from agno.run.agent import RunInput, RunOutput
from pydantic import ValidationError

from app.agents import memory
from app.guardrails.input import PiiGuardrail, input_guardrails
from app.guardrails.output import output_guardrail
from app.guardrails.pii import CustomPattern, find_pii, mask
from app.schemas.config import CustomPiiPattern, GuardrailSettings, OutputRule, PiiRule

MAT = CustomPattern("matrícula", "MAT", 6, 8)
PROTOCOLO = CustomPattern("protocolo", "", 10, 12)
CPF = "529.982.247-25"


@pytest.mark.parametrize(
    ("texto", "mascarado"),
    [
        ("minha MAT-123456", "minha [matrícula removido]"),
        ("mat: 1234.5678 ok", "[matrícula removido] ok"),
        ("protocolo 2024.000.123-45", "protocolo [protocolo removido]"),
    ],
)
def test_mascara_pelo_rotulo(texto: str, mascarado: str) -> None:
    out = mask(texto, find_pii(texto, custom=[MAT, PROTOCOLO]))
    assert mascarado in out


@pytest.mark.parametrize(
    "texto",
    [
        "MAT 12345",  # dígitos de menos
        "MAT 123456789",  # dígitos demais
        "PROTMAT123456",  # prefixo dentro de outra palavra
        "pedido 123456789",  # sem o prefixo e abaixo da faixa do padrão sem prefixo
    ],
)
def test_nao_mascara_fora_do_formato(texto: str) -> None:
    assert find_pii(texto, types=[], custom=[MAT, PROTOCOLO]) == []


def test_cpf_vence_o_padrao_proprio_que_casaria_nele() -> None:
    [match] = find_pii(f"cpf {CPF}", custom=[CustomPattern("conta", "", 11, 11)])
    assert match.type == "cpf"


def test_busca_linear_em_texto_hostil() -> None:
    hostil = ["1." * 50_000, "MAT " * 25_000, "1" * 100_000]
    started = time.perf_counter()
    for texto in hostil:
        find_pii(texto, custom=[MAT, PROTOCOLO, CustomPattern("x", "A-1", 4, 20)])
    assert time.perf_counter() - started < 2


@pytest.mark.parametrize(
    "item",
    [
        {"label": "x", "prefix": "MAT(", "min_digits": 6, "max_digits": 8},
        {"label": "x", "prefix": "ABCDEFGHIJK", "min_digits": 6, "max_digits": 8},
        {"label": "x", "min_digits": 3, "max_digits": 8},
        {"label": "x", "min_digits": 9, "max_digits": 8},
        {"label": "x", "min_digits": 6, "max_digits": 21},
        {"label": "a]b", "min_digits": 6, "max_digits": 8},
        {"label": "   ", "min_digits": 6, "max_digits": 8},
    ],
)
def test_padrao_invalido_e_recusado(item: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CustomPiiPattern.model_validate(item)


def test_limite_e_rotulo_repetido() -> None:
    item = {"label": "a", "min_digits": 6, "max_digits": 8}
    with pytest.raises(ValidationError):
        PiiRule(
            custom=[CustomPiiPattern.model_validate({**item, "label": f"p{i}"}) for i in range(11)]
        )
    with pytest.raises(ValidationError):
        PiiRule(
            custom=[
                CustomPiiPattern.model_validate(item),
                CustomPiiPattern.model_validate({**item, "label": "A"}),
            ]
        )


def _settings(mode: str = "mask", **output: object) -> GuardrailSettings:
    custom = [CustomPiiPattern(label="matrícula", prefix="MAT", min_digits=6, max_digits=8)]
    return GuardrailSettings.model_validate(
        {
            "pii": {"mode": mode, "types": [], "custom": [c.model_dump() for c in custom]},
            "output": OutputRule.model_validate(output).model_dump(),
        }
    )


def test_entrada_mascara_so_com_padrao_proprio() -> None:
    [hook] = input_guardrails(_settings())
    assert isinstance(hook, PiiGuardrail)
    run_input = RunInput(input_content="sou a MAT 7654321")
    hook.check(run_input)
    assert run_input.input_content == "sou a [matrícula removido]"


def test_entrada_bloqueia_com_o_tipo_do_padrao() -> None:
    [hook] = input_guardrails(_settings("block"))
    run_input = RunInput(input_content="MAT 7654321")
    with pytest.raises(InputCheckError):
        hook.check(run_input)
    assert "7654321" not in str(run_input.input_content)


def test_saida_barra_o_padrao_proprio() -> None:
    check = output_guardrail(_settings(pii=True, pii_types=[]))
    assert check is not None
    with pytest.raises(OutputCheckError):
        check(RunOutput(content="a matrícula é MAT 7654321"))


def test_memoria_mascara_pelo_agente_que_gravou() -> None:
    memory._custom_by_agent["agente-a"] = (MAT,)
    try:
        assert memory._masked("MAT 7654321", memory._custom_by_agent["agente-a"]) == (
            "[matrícula removido]"
        )
        assert memory._masked("MAT 7654321") == "MAT 7654321"
    finally:
        memory._custom_by_agent.pop("agente-a", None)
