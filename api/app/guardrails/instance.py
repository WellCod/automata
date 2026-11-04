"""Piso de guardrails da instância (ADR-0034) e a combinação com os do agente.

O agente só endurece o piso. A combinação acontece ao carregar a versão, então
entrada, saída, exame de tool, memória e suíte recebem o efetivo. As listas podem
passar dos limites da escrita: o efetivo não é validado de novo (`model_copy`).
"""

import time

from sqlalchemy.orm import Session

from app.db import get_engine
from app.models.instance_guardrails import InstanceGuardrails
from app.schemas.config import (
    ClassifierRule,
    GuardrailSettings,
    OutputClassifierRule,
    OutputRule,
    PiiRule,
    ToolResultScreening,
)

_TTL = 5.0
_cache: tuple[float, GuardrailSettings | None] | None = None
_PII_ORDER = {"off": 0, "mask": 1, "block": 2}


def _union[T](*lists: list[T]) -> list[T]:
    return list(dict.fromkeys(item for items in lists for item in items))


def floor() -> GuardrailSettings | None:
    """O piso gravado, com cache curto: outro worker vê a mudança em até 5 s."""
    global _cache
    if _cache is not None and time.monotonic() - _cache[0] < _TTL:
        return _cache[1]
    with Session(get_engine()) as session:
        row = session.get(InstanceGuardrails, 1)
        value = GuardrailSettings.model_validate(row.settings) if row is not None else None
    _cache = (time.monotonic(), value)
    return value


def forget() -> None:
    global _cache
    _cache = None


def _pii(base: PiiRule, own: PiiRule) -> PiiRule:
    mode = max(base.mode, own.mode, key=lambda m: _PII_ORDER[m])
    # tipos de um lado desligado não contam: o padrão do agente é "todos os tipos"
    types = _union(*(r.types for r in (base, own) if r.mode != "off"))
    labels = {p.label.lower() for p in base.custom}
    custom = [*base.custom, *(p for p in own.custom if p.label.lower() not in labels)]
    return own.model_copy(update={"mode": mode, "types": types, "custom": custom})


def merge_classifier[R: (ClassifierRule, OutputClassifierRule)](
    base: R | None, own: R | None
) -> R | None:
    """Com os dois: modelo e escopo do agente, união das checagens, falha bloqueia se um pedir."""
    if base is None or own is None:
        return own if base is None else base
    return own.model_copy(
        update={
            "checks": _union(own.checks, base.checks),
            "scope": own.scope if own.scope.strip() else base.scope,
            "on_failure": "block" if "block" in (own.on_failure, base.on_failure) else "allow",
        }
    )


def _tool_results(
    base: ToolResultScreening | None, own: ToolResultScreening | None
) -> ToolResultScreening | None:
    if base is None or own is None:
        return own if base is None else base
    return own.model_copy(
        update={"terms": base.terms or own.terms, "classifier": base.classifier or own.classifier}
    )


def _output(base: OutputRule, own: OutputRule) -> OutputRule:
    return own.model_copy(
        update={
            "pii": base.pii or own.pii,
            "pii_types": _union(*(r.pii_types for r in (base, own) if r.pii)),
            "blocked_terms": _union(base.blocked_terms, own.blocked_terms),
            "classifier": merge_classifier(base.classifier, own.classifier),
        }
    )


def effective(base: GuardrailSettings | None, own: GuardrailSettings) -> GuardrailSettings:
    if base is None:
        return own
    limits = [v for v in (base.max_input_chars, own.max_input_chars) if v is not None]
    return own.model_copy(
        update={
            "pii": _pii(base.pii, own.pii),
            "prompt_injection": base.prompt_injection or own.prompt_injection,
            "injection_extra_terms": _union(base.injection_extra_terms, own.injection_extra_terms),
            "blocked_topics": _union(base.blocked_topics, own.blocked_topics),
            "max_input_chars": min(limits) if limits else None,
            "moderation": base.moderation or own.moderation,
            "classifier": merge_classifier(base.classifier, own.classifier),
            "tool_results": _tool_results(base.tool_results, own.tool_results),
            "output": _output(base.output, own.output),
        }
    )
