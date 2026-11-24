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
# do mais brando ao mais duro: a combinação fica com o maior
_PII_ORDER = {"off": 0, "mask": 1, "block": 2}


def _union[T](*lists: list[T]) -> list[T]:
    """União das listas sem repetição, na ordem em que cada item aparece primeiro."""
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
    """Descarta o piso em cache; a escrita do piso chama para valer já neste worker."""
    global _cache
    _cache = None


def _pii(base: PiiRule, own: PiiRule) -> PiiRule:
    """Modo mais duro, tipos somados e padrões próprios do piso antes dos do agente."""
    mode = max(base.mode, own.mode, key=lambda pii_mode: _PII_ORDER[pii_mode])
    # tipos de um lado desligado não contam: o padrão do agente é "todos os tipos"
    types = _union(*(side.types for side in (base, own) if side.mode != "off"))
    # mesmo rótulo nos dois: fica o do piso
    floor_labels = {pattern.label.lower() for pattern in base.custom}
    custom = [
        *base.custom,
        *(pattern for pattern in own.custom if pattern.label.lower() not in floor_labels),
    ]
    return own.model_copy(update={"mode": mode, "types": types, "custom": custom})


def merge_classifier[R: (ClassifierRule, OutputClassifierRule)](
    base: R | None, own: R | None
) -> R | None:
    """Com os dois: modelo e escopo do piso, união das checagens, falha bloqueia se um pedir.

    O modelo e o escopo saem do piso (Fase 43): com os do agente, o editor escolhia um
    modelo sem chave na instância e, com falha aberta, toda checagem passava; ou trocava
    o escopo e anulava o `off_topic` do piso.
    """
    if base is None or own is None:
        return own if base is None else base
    return own.model_copy(
        update={
            "model_id": base.model_id,
            "checks": _union(own.checks, base.checks),
            "scope": base.scope if base.scope.strip() else own.scope,
            "on_failure": "block" if "block" in (own.on_failure, base.on_failure) else "allow",
        }
    )


def _tool_results(
    base: ToolResultScreening | None, own: ToolResultScreening | None
) -> ToolResultScreening | None:
    """Exame de tool ligado se um dos lados liga; termos e classificador valem se um pedir."""
    if base is None or own is None:
        return own if base is None else base
    return own.model_copy(
        update={"terms": base.terms or own.terms, "classifier": base.classifier or own.classifier}
    )


def _output(base: OutputRule, own: OutputRule) -> OutputRule:
    """Regras de saída somadas: a máscara, os termos e o classificador de qualquer lado."""
    return own.model_copy(
        update={
            "pii": base.pii or own.pii,
            "pii_types": _union(*(side.pii_types for side in (base, own) if side.pii)),
            "blocked_terms": _union(base.blocked_terms, own.blocked_terms),
            "classifier": merge_classifier(base.classifier, own.classifier),
        }
    )


def effective(base: GuardrailSettings | None, own: GuardrailSettings) -> GuardrailSettings:
    """Guardrails do agente endurecidos pelo piso `base`; sem piso, os do agente."""
    if base is None:
        return own
    limits = [limit for limit in (base.max_input_chars, own.max_input_chars) if limit is not None]

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
