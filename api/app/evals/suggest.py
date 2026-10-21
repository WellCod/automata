"""Sugestão de caso de teste a partir de um run real (ADR-0016).

Não grava nada: monta entrada, contexto e checagens para o formulário de caso, que o
editor revisa antes de salvar. Dados pessoais saem mascarados com todos os tipos,
mesmo que o agente não tenha guardrail de PII: o caso fica num cadastro que outros
editores veem, e a conversa original não.
"""

from dataclasses import dataclass, field
from typing import Any

from app.guardrails.pii import PII_TYPES, find_pii, mask
from app.schemas.eval import MAX_CONTEXT

# resposta de referência no critério do juiz: o bastante para julgar, sem copiar a conversa
_REFERENCE_CHARS = 600
_NAME_CHARS = 60


def masked(text: str) -> str:
    return mask(text, find_pii(text, PII_TYPES))


def _input_of(run: Any) -> str:
    raw = getattr(getattr(run, "input", None), "input_content", None)
    return "" if raw is None else str(raw)


def tools_called(run: Any) -> list[str]:
    """Tools que o run executou sem erro, na ordem, sem repetir."""
    names: list[str] = []
    for t in getattr(run, "tools", None) or []:
        name = getattr(t, "tool_name", None)
        if name and not getattr(t, "tool_call_error", False) and name not in names:
            names.append(name)
    return names


@dataclass
class Suggestion:
    name: str
    input: str
    context: list[str]
    checks: list[dict[str, Any]]
    # critério de rascunho para o juiz; o formulário decide se entra
    judge_criteria: str | None
    source_run_id: str
    notes: list[str] = field(default_factory=list)


def suggest(run: Any, previous: list[Any]) -> Suggestion:
    """`previous` são os runs anteriores da mesma sessão, do mais antigo ao mais recente."""
    message = masked(_input_of(run))
    context = [masked(_input_of(r)) for r in previous if _input_of(r)][-MAX_CONTEXT:]
    checks: list[dict[str, Any]] = [{"type": "text", "kind": "not_empty"}]
    tools = tools_called(run)
    if tools:
        # tools que o run chamou são objetivas; texto da resposta prenderia o caso à redação
        checks.append({"type": "tools", "tools": tools, "allow_additional": True})
    reply = masked("" if getattr(run, "content", None) is None else str(run.content))
    criteria = None
    if reply.strip():
        reference = reply[:_REFERENCE_CHARS] + ("…" if len(reply) > _REFERENCE_CHARS else "")
        criteria = (
            "Responde ao que foi pedido com o mesmo conteúdo essencial desta resposta de "
            f"referência, sem inventar informação: {reference}"
        )
    notes: list[str] = []
    asked = [_input_of(r) for r in previous if _input_of(r)]
    if len(asked) > MAX_CONTEXT:
        notes.append(f"Só as últimas {MAX_CONTEXT} mensagens anteriores entraram como contexto.")
    if any(find_pii(t, PII_TYPES) for t in [_input_of(run), *asked[-MAX_CONTEXT:]]):
        notes.append("Dados pessoais foram mascarados.")
    first_line = message.strip().splitlines()[0] if message.strip() else "caso da conversa"
    return Suggestion(
        name=first_line[:_NAME_CHARS],
        input=message,
        context=context,
        checks=checks,
        judge_criteria=criteria,
        source_run_id=str(getattr(run, "run_id", "")),
        notes=notes,
    )
