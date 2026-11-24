"""Guardrails de entrada (ADR-0013): viram pre_hooks do Agent e do Team.

Rodam antes de o Agno montar as mensagens e chamar o modelo; bloquear não custa
token. Só InputCheckError interrompe o run (qualquer outra exceção de hook o Agno
só loga), e a mensagem da exceção é o que o usuário vê: por isso ela é a
mensagem de bloqueio do agente, e o motivo técnico vai em additional_data.
"""

import os
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from agno.exceptions import CheckTrigger, InputCheckError
from agno.guardrails.base import BaseGuardrail
from agno.run.agent import RunInput
from agno.run.team import TeamRunInput

from app.guardrails.pii import PII_SCAN_MAX_CHARS, CustomPattern, PiiType, find_pii, mask
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
    """Texto em minúscula, sem acento, sem caractere invisível e com espaço único."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    # sem acento e sem caractere invisível (largura zero, marcas de direção), que
    # partiria o termo sem mudar o que o modelo lê (auditoria da Fase 33)
    stripped = "".join(
        char
        for char in decomposed
        if not unicodedata.combining(char) and unicodedata.category(char) != "Cf"
    )
    return " ".join(stripped.split())


def _block(message: str, trigger: CheckTrigger, rule: str, **extra: Any) -> InputCheckError:
    """Exceção de bloqueio: `message` é o que o usuário vê, o resto vai em additional_data."""
    return InputCheckError(message, check_trigger=trigger, additional_data={"rule": rule, **extra})


@dataclass
class Block:
    """Um bloqueio do run: a regra (vai para agent_run.blocked_by), a mensagem e o detalhe."""

    rule: str
    message: str
    detail: dict[str, Any]


@dataclass
class BlockLog:
    """Bloqueios do run, lidos pelo tracking (ADR-0013).

    O RunOutput bloqueado só traz a mensagem; o motivo fica aqui. O agente é
    montado por request, então o registro é de um run só.
    """

    blocks: list[Block] = field(default_factory=list)
    # resultados de tool retirados (ADR-0030): o run segue, mas o motivo fica gravado
    screened: list[dict[str, Any]] = field(default_factory=list)
    # run encerrado antes do fim por uma regra que não é erro (ADR-0031)
    stop_reason: str | None = None

    @property
    def last(self) -> Block | None:
        return self.blocks[-1] if self.blocks else None


class _Guardrail(BaseGuardrail):
    """Base dos guardrails de entrada: as subclasses implementam `_check`, e o bloqueio
    levantado é anotado no BlockLog antes de seguir para o Agno."""

    def __init__(self, blocked_message: str, log: BlockLog | None = None) -> None:
        self.blocked_message = blocked_message
        self.log = log

    def _check(self, run_input: AnyInput) -> None:
        raise NotImplementedError

    async def _acheck(self, run_input: AnyInput) -> None:
        self._check(run_input)

    def _note(self, exc: InputCheckError) -> None:
        """Copia o bloqueio para o registro do run, que o tracking grava."""
        if self.log is not None:
            detail = {
                key: value for key, value in (exc.additional_data or {}).items() if key != "rule"
            }
            rule = (exc.additional_data or {}).get("rule", exc.error_id)
            self.log.blocks.append(Block(str(rule), exc.message, detail))

    def check(self, run_input: AnyInput) -> None:
        try:
            self._check(run_input)
        except InputCheckError as exc:
            self._note(exc)
            raise

    async def async_check(self, run_input: AnyInput) -> None:
        try:
            await self._acheck(run_input)
        except InputCheckError as exc:
            self._note(exc)
            raise


class PiiGuardrail(_Guardrail):
    """Mascara sempre; no modo bloquear, levanta depois de mascarar.

    O Agno grava o run bloqueado com o input: mascarar antes de levantar faz a
    sessão guardar a versão sem o dado (ADR-0013).
    """

    def __init__(
        self,
        blocked_message: str,
        types: list[PiiType],
        block: bool,
        log: BlockLog | None = None,
        custom: tuple[CustomPattern, ...] = (),
    ) -> None:
        super().__init__(blocked_message, log)
        self.types = types
        self.block = block
        self.custom = custom

    def _check(self, run_input: AnyInput) -> None:
        if not isinstance(run_input.input_content, str):
            return
        size = len(run_input.input_content)
        # o scan é linear mas segura o GIL: texto acima do teto é barrado sem ser lido
        if size > PII_SCAN_MAX_CHARS:
            raise _block(
                self.blocked_message,
                CheckTrigger.INPUT_NOT_ALLOWED,
                RULE_LENGTH,
                size=size,
                limit=PII_SCAN_MAX_CHARS,
            )
        matches = find_pii(run_input.input_content, self.types, self.custom)
        if not matches:
            return
        run_input.input_content = mask(run_input.input_content, matches)
        if self.block:
            types = sorted({match.type for match in matches})
            raise _block(self.blocked_message, CheckTrigger.PII_DETECTED, RULE_PII, types=types)


class TermsGuardrail(_Guardrail):
    """Bloqueia quando um dos termos aparece no texto, os dois normalizados."""

    def __init__(
        self,
        blocked_message: str,
        terms: list[str],
        trigger: CheckTrigger,
        rule: str,
        log: BlockLog | None = None,
    ) -> None:
        super().__init__(blocked_message, log)
        normalized_terms = (normalize(term) for term in terms)
        self.terms = [term for term in normalized_terms if term]
        self.trigger = trigger
        self.rule = rule

    def _check(self, run_input: AnyInput) -> None:
        text = normalize(run_input.input_content_string())
        hit = next((term for term in self.terms if term in text), None)
        if hit is not None:
            raise _block(self.blocked_message, self.trigger, self.rule, term=hit)


class LengthGuardrail(_Guardrail):
    """Bloqueia mensagem com mais caracteres que o limite do agente."""

    def __init__(self, blocked_message: str, max_chars: int, log: BlockLog | None = None) -> None:
        super().__init__(blocked_message, log)
        self.max_chars = max_chars

    def _check(self, run_input: AnyInput) -> None:
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

    def __init__(self, blocked_message: str, log: BlockLog | None = None) -> None:
        super().__init__(blocked_message, log)
        from agno.guardrails import OpenAIModerationGuardrail

        self._inner = OpenAIModerationGuardrail()

    def _check(self, run_input: AnyInput) -> None:
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

    async def _acheck(self, run_input: AnyInput) -> None:
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
    """A moderação usa a API da OpenAI: sem a chave, não há como ligar."""
    return bool(os.environ.get("OPENAI_API_KEY"))


def input_guardrails(
    settings: GuardrailSettings, log: BlockLog | None = None, config_id: UUID | None = None
) -> list[BaseGuardrail]:
    """Ordem: dados pessoais primeiro, para o input ficar mascarado mesmo quando
    outra regra bloqueia; depois as regras por termo, que não custam nada; o
    classificador e a moderação por último, porque saem da API."""
    blocked_message = settings.blocked_message
    hooks: list[BaseGuardrail] = []
    if settings.pii.mode != "off" and (settings.pii.types or settings.pii.custom):
        hooks.append(
            PiiGuardrail(
                blocked_message,
                list(settings.pii.types),
                settings.pii.mode == "block",
                log,
                settings.pii.custom_patterns(),
            )
        )
    if settings.max_input_chars is not None:
        hooks.append(LengthGuardrail(blocked_message, settings.max_input_chars, log))
    if settings.prompt_injection:
        terms = [*INJECTION_TERMS, *settings.injection_extra_terms]
        hooks.append(
            TermsGuardrail(
                blocked_message, terms, CheckTrigger.PROMPT_INJECTION, RULE_INJECTION, log
            )
        )
    if settings.blocked_topics:
        hooks.append(
            TermsGuardrail(
                blocked_message, settings.blocked_topics, CheckTrigger.OFF_TOPIC, RULE_TOPIC, log
            )
        )
    if settings.classifier is not None:
        from app.guardrails.classifier import ClassifierGuardrail, classifier_enabled

        if classifier_enabled():
            hooks.append(ClassifierGuardrail(settings.classifier, blocked_message, log, config_id))
    if settings.moderation:
        hooks.append(ModerationGuardrail(blocked_message, log))

    return hooks
