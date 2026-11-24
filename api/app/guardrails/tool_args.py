"""Argumentos de tool passam pelos termos bloqueados e pela máscara da saída (LLM-06).

O guardrail de saída só olhava `run_output.content`: conteúdo injetado podia fazer o
agente pôr histórico ou trecho da base nos argumentos de uma tool de envio. Com termo
bloqueado nos argumentos a tool não roda e o modelo recebe um aviso; com a máscara de
dados pessoais ligada na saída, os textos dos argumentos chegam mascarados à tool.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.guardrails.input import BlockLog, normalize
from app.guardrails.pii import CustomPattern, PiiType, find_pii, mask
from app.schemas.config import GuardrailSettings

logger = logging.getLogger(__name__)

RULE_TOOL_ARGS_TERM = "tool_args_blocked_term"
RULE_TOOL_ARGS_PII = "tool_args_pii"


def blocked_warning(tool: str) -> str:
    """Texto que o modelo recebe no lugar do resultado da tool barrada."""
    return (
        f"A chamada a {tool} não foi feita: os argumentos tinham conteúdo que este agente não"
        " pode enviar. Responda ao usuário sem essa ação."
    )


def _mask_value(value: Any, types: list[PiiType], custom: list[CustomPattern]) -> Any:
    """Mascara os textos do argumento, descendo por listas e dicts; o resto passa igual."""
    if isinstance(value, str):
        found = find_pii(value, types, custom)
        return mask(value, found) if found else value
    if isinstance(value, list):
        return [_mask_value(item, types, custom) for item in value]
    if isinstance(value, dict):
        return {key: _mask_value(item, types, custom) for key, item in value.items()}
    return value


@dataclass
class ArgumentGuard:
    """Gancho de tool que barra termo bloqueado e mascara dado pessoal nos argumentos."""

    terms: list[str]
    pii_types: list[PiiType]
    custom: list[CustomPattern]
    log: BlockLog

    def _note(self, tool: str, rule: str, term: str | None) -> None:
        """Registra a intervenção no run, sem guardar os argumentos."""
        self.log.screened.append(
            {"tool": tool, "rule": rule, "term": term, "at": datetime.now(UTC).isoformat()}
        )
        logger.info("argumento de tool barrado", extra={"tool": tool, "rule": rule})

    def check(self, tool: str, arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """(argumentos a usar, motivo); None quando a tool não deve rodar."""
        if self.terms:
            text = normalize(json.dumps(arguments, ensure_ascii=False, default=str))
            for term in self.terms:
                if term in text:
                    self._note(tool, RULE_TOOL_ARGS_TERM, term)
                    return None, RULE_TOOL_ARGS_TERM
        if self.pii_types or self.custom:
            masked = _mask_value(arguments, self.pii_types, self.custom)
            if masked != arguments:
                self._note(tool, RULE_TOOL_ARGS_PII, None)
                return masked, RULE_TOOL_ARGS_PII
        return arguments, ""

    def hook(self) -> Callable[..., Any]:
        """Gancho para `tool_hooks`; o Agno passa os argumentos pelo nome da assinatura."""

        # síncrono serve às duas cadeias do Agno: decide antes de chamar e devolve a
        # corrotina da tool sem esperar, quando é o caso
        def guard_args(
            function_name: str, function_call: Callable[..., Any], arguments: Any
        ) -> Any:
            tool_arguments = dict(arguments or {})
            allowed, _ = self.check(function_name, tool_arguments)
            if allowed is None:
                return blocked_warning(function_name)
            return function_call(**allowed)

        return guard_args


def argument_guard(settings: GuardrailSettings, log: BlockLog) -> ArgumentGuard | None:
    """Guarda dos argumentos com os termos e a máscara da saída; None sem nenhum dos dois."""
    output = settings.output
    normalized_terms = (normalize(term) for term in output.blocked_terms)
    terms = [term for term in normalized_terms if term]

    types: list[PiiType] = list(output.pii_types) if output.pii else []
    custom = list(settings.pii.custom_patterns()) if output.pii else []
    if not terms and not types and not custom:
        return None
    return ArgumentGuard(terms, types, custom, log)
