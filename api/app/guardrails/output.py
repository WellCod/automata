"""Guardrail de saída (ADR-0013): vira post_hook do Agent e do Team.

Os guardrails prontos do Agno não servem aqui: em post_hook o check() é chamado
sem run_input e o erro é engolido. Esta função recebe o run_output.

O Agno só troca o conteúdo pelo texto da exceção quando ele está vazio; a
resposta bloqueada sairia mesmo assim. Por isso o hook troca a resposta (e a
mensagem do assistente que vai para a sessão) antes de levantar. No stream o
texto já foi entregue enquanto era gerado: ali o hook só marca o run.
"""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from agno.exceptions import CheckTrigger, OutputCheckError

from app.guardrails.input import Block, BlockLog, normalize
from app.guardrails.pii import find_pii
from app.schemas.config import GuardrailSettings, OutputClassifierRule
from app.side_usage import Caller, record_side_usage

RULE_OUTPUT = "output_not_allowed"
RULE_OUTPUT_CLASSIFIER = "output_classifier"

logger = logging.getLogger(__name__)


def _violation(text: str, settings: GuardrailSettings) -> dict[str, Any] | None:
    rule = settings.output
    if rule.pii:
        # os padrões próprios do agente valem também na saída (ADR-0032)
        matches = find_pii(text, rule.pii_types, settings.pii.custom_patterns())
        if matches:
            return {"types": sorted({m.type for m in matches})}
    if rule.blocked_terms:
        normalized = normalize(text)
        for term in rule.blocked_terms:
            if normalize(term) in normalized:
                return {"term": normalize(term)}
    return None


def _content(run_output: Any) -> str | None:
    content = getattr(run_output, "content", None)
    # com saída estruturada a resposta é objeto (ADR-0027): o dado pessoal está nos valores
    if isinstance(content, dict | list):
        content = json.dumps(content, ensure_ascii=False)
    if not isinstance(content, str) or not content:
        return None
    return content


def _replace(run_output: Any, message: str, hit: Callable[[str], bool]) -> None:
    """Troca a resposta e a mensagem do assistente que vai para a sessão, antes de levantar:
    o Agno só troca o conteúdo pelo texto da exceção quando ele está vazio."""
    run_output.content = message
    for msg in getattr(run_output, "messages", None) or []:
        role = getattr(msg, "role", None)
        if role == "assistant" and isinstance(msg.content, str) and hit(msg.content):
            msg.content = message


def _raise(log: BlockLog | None, rule: str, message: str, detail: dict[str, Any]) -> None:
    if log is not None:
        log.blocks.append(Block(rule, message, detail))
    raise OutputCheckError(
        message,
        check_trigger=CheckTrigger.OUTPUT_NOT_ALLOWED,
        additional_data={"rule": rule, **detail},
    )


def output_guardrail(
    settings: GuardrailSettings, log: BlockLog | None = None, config_id: UUID | None = None
) -> Callable[..., Any] | None:
    rule = settings.output
    classifier = rule.classifier
    if classifier is not None:
        from app.guardrails.classifier import classifier_enabled

        # o replay da demo não tem resposta gravada para o classificador
        if not classifier_enabled():
            classifier = None
    if not (rule.pii or rule.blocked_terms or classifier):
        return None
    message = settings.blocked_message

    def check_rules(run_output: Any) -> None:
        content = _content(run_output)
        if content is None:
            return
        detail = _violation(content, settings)
        if detail is None:
            return
        _replace(run_output, message, lambda text: _violation(text, settings) is not None)
        _raise(log, RULE_OUTPUT, message, detail)

    if classifier is None:
        # o Agno passa só os argumentos que a função declara, pelo nome
        def check_output(run_output: Any) -> None:
            check_rules(run_output)

        return check_output

    judge = OutputClassifier(classifier, config_id)

    # assíncrono: o arun do Agno espera; o run() síncrono pularia, e o app não o usa
    async def check_output_classified(run_output: Any, run_context: Any = None) -> None:
        check_rules(run_output)
        content = _content(run_output)
        if content is None or not content.strip():
            return
        detail = await judge.verdict(content, run_context)
        if detail is None:
            return
        _replace(run_output, message, lambda text: text == content)
        _raise(log, RULE_OUTPUT_CLASSIFIER, message, detail)

    return check_output_classified


# blocos de 20 mil caracteres examinados na resposta; acima disso, vale o on_failure
MAX_OUTPUT_BLOCKS = 5


class OutputClassifier:
    """Classificador da resposta (ADR-0034), com as regras de falha do de entrada."""

    def __init__(self, rule: OutputClassifierRule, config_id: UUID | None) -> None:
        self.rule = rule
        self.config_id = config_id

    def _record(self, usage: Any, run_context: Any) -> None:
        if self.config_id is None:
            return
        caller = Caller(
            self.config_id,
            getattr(run_context, "user_id", None) or "anonymous",
            getattr(run_context, "run_id", None),
        )
        try:
            record_side_usage(caller, self.rule.model_id, usage)
        except Exception as exc:
            logger.warning("consumo do classificador não gravado", extra={"error": str(exc)})

    async def verdict(self, text: str, run_context: Any = None) -> dict[str, Any] | None:
        """Detalhe do bloqueio, ou None para deixar a resposta passar."""
        from app.agents.models_map import resolve_model
        from app.evals.judge import metered
        from app.guardrails.classifier import (
            MAX_CLASSIFIED_CHARS,
            ClassifierBadOutput,
            ClassifierUnavailable,
            aclassify,
        )

        usage = None
        blocks = [
            text[i : i + MAX_CLASSIFIED_CHARS] for i in range(0, len(text), MAX_CLASSIFIED_CHARS)
        ]
        try:
            if len(blocks) > MAX_OUTPUT_BLOCKS:
                # resposta grande demais para examinar inteira: vale a regra de falha
                raise ClassifierUnavailable(f"resposta com mais de {len(blocks)} blocos")
            model, usage = metered(resolve_model(self.rule.model_id))
            # a resposta inteira, em blocos: com começo e fim só, o vazamento ia no meio (Fase 43)
            for block in blocks:
                result = await aclassify(model, self.rule, block)
                if result.block:
                    break
        except ClassifierBadOutput as exc:
            return {"category": "invalid_output", "reason": str(exc)[:300]}
        except (ClassifierUnavailable, ValueError) as exc:
            logger.warning(
                "classificador da saída indisponível",
                extra={"config_id": str(self.config_id), "error": str(exc)[:300]},
            )
            if self.rule.on_failure == "block":
                return {"category": "unavailable", "reason": str(exc)[:300]}
            return None
        finally:
            if usage is not None:
                await asyncio.to_thread(self._record, usage, run_context)
        if result.block:
            return {"category": result.category, "reason": result.reason}
        return None
