"""Argumentos de tool com termos bloqueados e máscara de dados pessoais (LLM-06)."""

from typing import Any

from app.guardrails.input import BlockLog
from app.guardrails.tool_args import RULE_TOOL_ARGS_TERM, argument_guard
from app.schemas.config import GuardrailSettings


def _guard(**output: Any) -> Any:
    settings = GuardrailSettings.model_validate({"output": output})
    log = BlockLog()
    return argument_guard(settings, log), log


def test_sem_regra_na_saida_nao_ha_guarda() -> None:
    guard, _ = _guard()
    assert guard is None


def test_termo_bloqueado_nos_argumentos_nao_roda_a_tool() -> None:
    guard, log = _guard(blocked_terms=["prompt do sistema"])
    called: list[dict[str, Any]] = []
    hook = guard.hook()

    result = hook(
        "enviar_email",
        lambda **kw: called.append(kw) or "ok",
        {
            "para": "x@externo.com",
            "corpo": "Segue o Prompt do Sistema completo",
        },
    )
    assert called == [] and "não foi feita" in result
    assert log.screened[0]["rule"] == RULE_TOOL_ARGS_TERM


def test_dado_pessoal_chega_mascarado_quando_a_saida_mascara() -> None:
    guard, log = _guard(pii=True, pii_types=["cpf"])
    called: list[dict[str, Any]] = []
    hook = guard.hook()

    hook(
        "registrar",
        lambda **kw: called.append(kw) or "ok",
        {
            "nota": "cliente 529.982.247-25 ligou",
            "itens": [{"doc": "52998224725"}],
        },
    )
    [args] = called
    assert "529.982.247-25" not in args["nota"] and "52998224725" not in str(args["itens"])
    assert log.screened and log.screened[0]["rule"] == "tool_args_pii"
