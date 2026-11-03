"""Registro das decisões humanas no workflow (ADR-0028).

O continue do AgentOS recebe a lista inteira de requisitos, inclusive os decididos em
rodadas anteriores. Só vira entrada o requisito ativo, o último, e só se estava pendente
no run: assim cada decisão entra uma vez, na ordem em que aconteceu.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db import get_engine
from app.guardrails.pii import PII_SCAN_MAX_CHARS, find_pii, mask
from app.repositories.run import RunRepository

# o antes e o depois da edição; a página mostra o diff, o resto fica no run do Agno
REVIEW_TEXT_CHARS = 20_000


def _get(item: Any, name: str) -> Any:
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _masked(value: Any) -> str | None:
    if value is None:
        return None
    text = (value if isinstance(value, str) else str(value))[:PII_SCAN_MAX_CHARS]
    # o rótulo da máscara é mais longo que o dado: o corte do registro vem depois dela
    return mask(text, find_pii(text))[:REVIEW_TEXT_CHARS]


def _decision(req: Any) -> str | None:
    confirmed = _get(req, "confirmed")
    if confirmed is None:
        return None
    if _get(req, "step_type") == "Loop":
        # aprovar a volta encerra o laço; recusar pede outra (Agno 3.1.8)
        return "loop_done" if confirmed else "loop_again"
    if confirmed and _get(req, "edited_output") is not None:
        return "edited"
    return "approved" if confirmed else "rejected"


def review_entries(
    requirements: list[Any] | None, pending_ids: set[str], actor: str | None
) -> list[dict[str, Any]]:
    at = datetime.now(UTC).isoformat()
    entries: list[dict[str, Any]] = []
    # revisão só no nível principal: uma pausa ativa por vez, e ela é o último requisito.
    # Os anteriores voltam na lista já decididos, às vezes com o mesmo step_id (refazer)
    for req in (requirements or [])[-1:]:
        if str(_get(req, "step_id")) not in pending_ids:
            continue
        decision = _decision(req)
        if decision is None:
            continue
        entry: dict[str, Any] = {
            "step_id": str(_get(req, "step_id")),
            "step_name": _get(req, "step_name"),
            "decision": decision,
            "by": actor or "desconhecido",
            "at": at,
        }
        feedback = _masked(_get(req, "rejection_feedback"))
        if feedback:
            entry["feedback"] = feedback
        if decision == "edited":
            step_output = _get(req, "step_output")
            entry["before"] = _masked(_get(step_output, "content") if step_output else None)
            entry["after"] = _masked(_get(req, "edited_output"))
        entries.append(entry)
    return entries


def record_reviews(run_id: str, requirements: list[Any] | None, actor: str | None) -> int:
    """Grava as decisões desta rodada no run; devolve quantas entraram."""
    with Session(get_engine()) as session:
        repo = RunRepository(session)
        entries = review_entries(requirements, repo.pending_step_ids(run_id), actor)
        if entries:
            repo.append_reviews(run_id, entries)
            session.commit()
        return len(entries)
