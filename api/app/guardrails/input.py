"""Guardrails de entrada (ADR-0013): viram pre_hooks do Agent e do Team.

Rodam antes de o Agno montar as mensagens e chamar o modelo; bloquear não custa
token. Só InputCheckError interrompe o run (qualquer outra exceção de hook o Agno
só loga), e a mensagem da exceção é o que o usuário vê: por isso ela é a
mensagem de bloqueio do agente, e o motivo técnico vai em additional_data.
"""

import os
import unicodedata
from typing import Any

from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails.base import BaseGuardrail
from agno.run.agent import RunInput
from agno.run.team import TeamRunInput

from app.guardrails.pii import PiiType, find_pii, mask
from app.schemas.config import GuardrailSettings

AnyInput = RunInput | TeamRunInput

# Motivos gravados em agent_run.blocked_by
RULE_PII = "pii_detected"
RULE_INJECTION = "prompt_injection"
RULE_TOPIC = "off_topic"
RULE_LENGTH = "input_too_long"
RULE_MODERATION = "moderation"

# Curta e conservadora: termo genérico demais bloqueia quem tem motivo legítimo.
# Comparada sem acento e sem maiúscula.
INJECTION_TERMS: tuple[str, ...] = (
    "ignore as instrucoes",
    "ignore suas instrucoes",
    "ignore todas as instrucoes",
    "ignore as regras",
    "esqueca as instrucoes",
    "esqueca tudo acima",
    "desconsidere as instrucoes",
    "revele seu prompt",
    "mostre seu prompt",
    "modo desenvolvedor",
    "sem restricoes",
    "ignore previous instructions",
    "ignore your instructions",
    "ignore all instructions",
    "disregard previous instructions",
    "forget everything above",
    "reveal your system prompt",
    "developer mode",
    "jailbreak",
    "bypass restrictions",
)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.split())


def _block(message: str, trigger: CheckTrigger, rule: str, **extra: Any) -> InputCheckError:
    return InputCheckError(message, check_trigger=trigger, additional_data={"rule": rule, **extra})


class _Guardrail(BaseGuardrail):
    def __init__(self, blocked_message: str) -> None:
        self.blocked_message = blocked_message

    async def async_check(self, run_input: AnyInput) -> None:
        self.check(run_input)


class PiiGuardrail(_Guardrail):
    """Mascara sempre; no modo bloquear, levanta depois de mascarar.

    O Agno grava o run bloqueado com o input: mascarar antes de levantar faz a
    sessão guardar a versão sem o dado (ADR-0013).
    """

    def __init__(self, blocked_message: str, types: list[PiiType], block: bool) -> None:
        super().__init__(blocked_message)
        self.types = types
        self.block = block

    def check(self, run_input: AnyInput) -> None:
        if not isinstance(run_input.input_content, str):
            return
        matches = find_pii(run_input.input_content, self.types)
        if not matches:
            return
        run_input.input_content = mask(run_input.input_content, matches)
        if self.block:
            types = sorted({m.type for m in matches})
            raise _block(self.blocked_message, CheckTrigger.PII_DETECTED, RULE_PII, types=types)


class TermsGuardrail(_Guardrail):
    def __init__(
        self, blocked_message: str, terms: list[str], trigger: CheckTrigger, rule: str
    ) -> None:
        super().__init__(blocked_message)
        self.terms = [t for t in (normalize(t) for t in terms) if t]
        self.trigger = trigger
        self.rule = rule

    def check(self, run_input: AnyInput) -> None:
        text = normalize(run_input.input_content_string())
        hit = next((t for t in self.terms if t in text), None)
        if hit is not None:
            raise _block(self.blocked_message, self.trigger, self.rule, term=hit)


class LengthGuardrail(_Guardrail):
    def __init__(self, blocked_message: str, max_chars: int) -> None:
        super().__init__(blocked_message)
        self.max_chars = max_chars

    def check(self, run_input: AnyInput) -> None:
        size = len(run_input.input_content_string())
        if size > self.max_chars:
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_LENGTH,
                size=size,
                limit=self.max_chars,
            )


class ModerationGuardrail(_Guardrail):
    """Moderação da OpenAI, com a mensagem do agente no lugar da técnica."""

    def __init__(self, blocked_message: str) -> None:
        super().__init__(blocked_message)
        from agno.guardrails import OpenAIModerationGuardrail

        self._inner = OpenAIModerationGuardrail()

    def check(self, run_input: AnyInput) -> None:
        try:
            self._inner.check(run_input)
        except InputCheckError as exc:
            categories = (exc.additional_data or {}).get("categories")
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_MODERATION,
                categories=categories,
            ) from exc

    async def async_check(self, run_input: AnyInput) -> None:
        try:
            await self._inner.async_check(run_input)
        except InputCheckError as exc:
            categories = (exc.additional_data or {}).get("categories")
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_MODERATION,
                categories=categories,
            ) from exc


def moderation_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def input_guardrails(settings: GuardrailSettings) -> list[BaseGuardrail]:
    """Ordem: dados pessoais primeiro, para o input ficar mascarado mesmo quando
    outra regra bloqueia; moderação por último, porque é a única que sai da API."""
    msg = settings.blocked_message
    hooks: list[BaseGuardrail] = []
    if settings.pii.mode != "off" and settings.pii.types:
        hooks.append(PiiGuardrail(msg, list(settings.pii.types), settings.pii.mode == "block"))
    if settings.max_input_chars is not None:
        hooks.append(LengthGuardrail(msg, settings.max_input_chars))
    if settings.prompt_injection:
        terms = [*INJECTION_TERMS, *settings.injection_extra_terms]
        hooks.append(TermsGuardrail(msg, terms, CheckTrigger.PROMPT_INJECTION, RULE_INJECTION))
    if settings.blocked_topics:
        hooks.append(
            TermsGuardrail(msg, settings.blocked_topics, CheckTrigger.OFF_TOPIC, RULE_TOPIC)
        )
    if settings.moderation:
        hooks.append(ModerationGuardrail(msg))
    return hooks
