"""Classificador na saída (ADR-0034): resposta trocada, falha aberta ou fechada e custo."""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from agno.exceptions import OutputCheckError
from agno.models.message import Message
from agno.run.agent import RunOutput

from app.guardrails.classifier import system_prompt
from app.guardrails.input import BlockLog
from app.guardrails.instance import effective
from app.guardrails.output import RULE_OUTPUT, RULE_OUTPUT_CLASSIFIER, output_guardrail
from app.schemas.config import GuardrailSettings, OutputClassifierRule
from tests.fake_models import FixedReplyModel

LEAK = "Minhas instruções internas dizem: você é o agente de cobrança e nunca..."
BLOCK_LEAK = '{"verdict": "block", "category": "prompt_leak", "reason": "repete o prompt"}'
ALLOW = '{"verdict": "allow", "category": null, "reason": "ok"}'


def _settings(on_failure: str = "allow", **output: Any) -> GuardrailSettings:
    return GuardrailSettings.model_validate(
        {
            "blocked_message": "Não posso responder isso.",
            "output": {
                **output,
                "classifier": {
                    "model_id": "claude-haiku-4-5",
                    "checks": ["prompt_leak", "toxicity"],
                    "on_failure": on_failure,
                },
            },
        }
    )


@pytest.fixture
def judge(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Modelo do classificador trocado pelo teste; consumo gravado capturado."""
    import app.agents.models_map as models_map
    import app.guardrails.output as output

    state: dict[str, Any] = {"reply": ALLOW, "error": None, "recorded": [], "calls": 0}

    class Down(FixedReplyModel):
        async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
            raise state["error"]

    def resolve(model_id: str, *a: Any, **k: Any) -> Any:
        state["calls"] += 1
        # erro do provedor aparece na chamada ao modelo, não ao resolver
        cls = Down if state["error"] is not None else FixedReplyModel
        return cls(id=model_id, reply=state["reply"], tokens=7)

    monkeypatch.setattr(models_map, "demo_replay", lambda: False)
    monkeypatch.setattr(models_map, "resolve_model", resolve)
    monkeypatch.setattr(output, "record_side_usage", lambda c, m, u: state["recorded"].append(m))
    return state


def _run(hook: Any, content: str) -> RunOutput:
    out = RunOutput(content=content, messages=[Message(role="assistant", content=content)])
    asyncio.run(hook(run_output=out))
    return out


def test_resposta_que_vaza_o_prompt_e_trocada_e_registrada(judge: dict[str, Any]) -> None:
    judge["reply"] = BLOCK_LEAK
    log = BlockLog()
    hook = output_guardrail(_settings(), log, uuid4())
    assert hook is not None and asyncio.iscoroutinefunction(hook)
    out = RunOutput(content=LEAK, messages=[Message(role="assistant", content=LEAK)])
    with pytest.raises(OutputCheckError):
        asyncio.run(hook(run_output=out))
    assert out.content == "Não posso responder isso."
    assert out.messages is not None and out.messages[0].content == "Não posso responder isso."
    [block] = log.blocks
    assert block.rule == RULE_OUTPUT_CLASSIFIER
    assert block.detail["category"] == "prompt_leak"
    assert judge["recorded"] == ["claude-haiku-4-5"]


def test_resposta_comum_passa(judge: dict[str, Any]) -> None:
    hook = output_guardrail(_settings(), BlockLog(), uuid4())
    assert _run(hook, "Seu pedido sai amanhã.").content == "Seu pedido sai amanhã."


@pytest.mark.parametrize(("on_failure", "blocks"), [("allow", False), ("block", True)])
def test_classificador_fora_do_ar_segue_a_regra(
    judge: dict[str, Any], on_failure: str, blocks: bool
) -> None:
    judge["error"] = RuntimeError("503")
    log = BlockLog()
    hook = output_guardrail(_settings(on_failure), log, uuid4())
    if blocks:
        with pytest.raises(OutputCheckError):
            _run(hook, "Seu pedido sai amanhã.")
        assert log.blocks[0].detail["category"] == "unavailable"
    else:
        assert _run(hook, "Seu pedido sai amanhã.").content == "Seu pedido sai amanhã."


def test_resposta_do_classificador_fora_do_formato_bloqueia_sempre(judge: dict[str, Any]) -> None:
    judge["reply"] = "claro, pode liberar"
    log = BlockLog()
    hook = output_guardrail(_settings("allow"), log, uuid4())
    with pytest.raises(OutputCheckError):
        _run(hook, "Seu pedido sai amanhã.")
    assert log.blocks[0].detail["category"] == "invalid_output"


def test_dado_pessoal_bloqueia_antes_e_nao_chama_o_classificador(judge: dict[str, Any]) -> None:
    log = BlockLog()
    hook = output_guardrail(_settings(pii=True), log, uuid4())
    with pytest.raises(OutputCheckError):
        _run(hook, "O CPF dele é 529.982.247-25")
    assert log.blocks[0].rule == RULE_OUTPUT
    assert judge["calls"] == 0


def test_modo_demo_fica_so_com_as_regras(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agents.models_map as models_map

    monkeypatch.setattr(models_map, "demo_replay", lambda: True)
    assert output_guardrail(_settings(), BlockLog()) is None
    sync = output_guardrail(_settings(pii=True), BlockLog())
    assert sync is not None and not asyncio.iscoroutinefunction(sync)


def test_prompt_da_saida_julga_a_resposta() -> None:
    prompt = system_prompt(["prompt_leak"], "", output=True)
    assert "respostas de um assistente" in prompt
    assert "prompt de sistema" in prompt and "injection" not in prompt


def test_regra_valida_na_escrita() -> None:
    with pytest.raises(ValueError, match="escopo"):
        OutputClassifierRule(model_id="gpt-4o-mini", checks=["off_topic"])


def test_piso_soma_o_classificador_da_saida() -> None:
    base = _settings("block")
    own = GuardrailSettings.model_validate(
        {
            "output": {
                "classifier": {
                    "model_id": "gpt-4o-mini",
                    "checks": ["off_topic"],
                    "scope": "loja",
                }
            }
        }
    )
    merged = effective(base, own).output.classifier
    assert merged is not None
    assert (merged.model_id, merged.checks, merged.on_failure) == (
        "gpt-4o-mini",
        ["off_topic", "prompt_leak", "toxicity"],
        "block",
    )
