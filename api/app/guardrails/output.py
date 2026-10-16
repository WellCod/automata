"""Guardrail de saída (ADR-0013): vira post_hook do Agent e do Team.

Os guardrails prontos do Agno não servem aqui: em post_hook o check() é chamado
sem run_input e o erro é engolido. Esta função recebe o run_output.

O Agno só troca o conteúdo pelo texto da exceção quando ele está vazio; a
resposta bloqueada sairia mesmo assim. Por isso o hook troca a resposta (e a
mensagem do assistente que vai para a sessão) antes de levantar. No stream o
texto já foi entregue enquanto era gerado: ali o hook só marca o run.
"""

from collections.abc import Callable
from typing import Any

from agno.exceptions import CheckTrigger, OutputCheckError

from app.guardrails.input import Block, BlockLog, normalize
from app.guardrails.pii import find_pii
from app.schemas.config import GuardrailSettings

RULE_OUTPUT = "output_not_allowed"


def _violation(text: str, settings: GuardrailSettings) -> dict[str, Any] | None:
    rule = settings.output
    if rule.pii:
        matches = find_pii(text, rule.pii_types)
        if matches:
            return {"types": sorted({m.type for m in matches})}
    if rule.blocked_terms:
        normalized = normalize(text)
        for term in rule.blocked_terms:
            if normalize(term) in normalized:
                return {"term": normalize(term)}
    return None


def output_guardrail(
    settings: GuardrailSettings, log: BlockLog | None = None
) -> Callable[..., None] | None:
    rule = settings.output
    if not (rule.pii or rule.blocked_terms):
        return None
    message = settings.blocked_message

    # o Agno passa só os argumentos que a função declara, pelo nome
    def check_output(run_output: Any) -> None:
        content = getattr(run_output, "content", None)
        if not isinstance(content, str) or not content:
            return
        detail = _violation(content, settings)
        if detail is None:
            return
        run_output.content = message
        for msg in getattr(run_output, "messages", None) or []:
            role = getattr(msg, "role", None)
            if (
                role == "assistant"
                and isinstance(msg.content, str)
                and _violation(msg.content, settings)
            ):
                msg.content = message
        if log is not None:
            log.blocks.append(Block(RULE_OUTPUT, message, detail))
        raise OutputCheckError(
            message,
            check_trigger=CheckTrigger.OUTPUT_NOT_ALLOWED,
            additional_data={"rule": RULE_OUTPUT, **detail},
        )

    return check_output
