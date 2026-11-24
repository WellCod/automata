"""Registro das decisões humanas no workflow (ADR-0028).

O continue do AgentOS recebe a lista inteira de requisitos, inclusive os decididos em
rodadas anteriores. Só vira entrada o requisito ativo, o último, e só se estava pendente
no run: assim cada decisão entra uma vez, na ordem em que aconteceu.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db import get_engine
from app.guardrails.pii import PII_SCAN_MAX_CHARS, find_pii, mask
from app.repositories.run import RunRepository

# o antes e o depois da edição; a página mostra o diff, o resto fica no run do Agno
REVIEW_TEXT_CHARS = 20_000


def _get(item: Any, name: str) -> Any:
    # o requisito chega como objeto do Agno ou como dict do corpo do continue
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _masked(value: Any) -> str | None:
    """Texto do registro com os dados pessoais mascarados e cortado no tamanho guardado."""
    if value is None:
        return None
    text = (value if isinstance(value, str) else str(value))[:PII_SCAN_MAX_CHARS]
    # o rótulo da máscara é mais longo que o dado: o corte do registro vem depois dela
    return mask(text, find_pii(text))[:REVIEW_TEXT_CHARS]


def _decision(requirement: Any, loop: bool) -> str | None:
    """Decisão registrada para o requisito; None quando ele ainda não foi decidido."""
    confirmed = _get(requirement, "confirmed")
    if confirmed is None:
        return None
    if loop:
        # aprovar a volta encerra o laço; recusar pede outra (Agno 3.1.8)
        return "loop_done" if confirmed else "loop_again"
    if confirmed and _get(requirement, "edited_output") is not None:
        return "edited"
    return "approved" if confirmed else "rejected"


def review_entries(
    requirements: list[Any] | None, pending: Mapping[str, dict[str, Any]], actor: str | None
) -> list[dict[str, Any]]:
    """`pending` são as etapas pausadas que o tracking gravou no run: o nome, o tipo e o
    texto antes da edição vêm dali. Do cliente só valem a decisão, o motivo e a edição
    (auditoria da Fase 33)."""
    decided_at = datetime.now(UTC).isoformat()
    entries: list[dict[str, Any]] = []
    # revisão só no nível principal: uma pausa ativa por vez, e ela é o último requisito.
    # Os anteriores voltam na lista já decididos, às vezes com o mesmo step_id (refazer)
    for requirement in (requirements or [])[-1:]:
        stored = pending.get(str(_get(requirement, "step_id")))
        if stored is None:
            continue
        decision = _decision(requirement, stored.get("when") == "loop")
        if decision is None:
            continue
        entry: dict[str, Any] = {
            "step_id": str(_get(requirement, "step_id")),
            "step_name": stored.get("step_name"),
            "decision": decision,
            "by": actor or "desconhecido",
            "at": decided_at,
        }
        feedback = _masked(_get(requirement, "rejection_feedback"))
        if feedback:
            entry["feedback"] = feedback
        if decision == "edited":
            entry["before"] = _masked(stored.get("output"))
            entry["after"] = _masked(_get(requirement, "edited_output"))
        entries.append(entry)
    return entries


def record_reviews(run_id: str, requirements: list[Any] | None, actor: str | None) -> int:
    """Grava as decisões desta rodada no run; devolve quantas entraram."""
    with Session(get_engine()) as session:
        repo = RunRepository(session)
        pending = {str(step.get("step_id")): step for step in repo.pending_steps(run_id)}

        entries = review_entries(requirements, pending, actor)
        if entries:
            repo.append_reviews(run_id, entries)
            session.commit()
        return len(entries)
