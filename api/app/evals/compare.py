"""Comparação caso a caso entre duas execuções e estado da suíte de cada config.

A comparação serve à tela (vigente × rascunho) e ao estado da suíte: a execução
agendada mais recente contra a agendada anterior (ADR-0016).
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.eval import EvalResult, EvalRun
from app.repositories.eval import EvalRunRepository


def change(base: str | None, target: str | None) -> str:
    """Classifica a mudança de status de um caso entre a execução base e a alvo."""
    if base is None:
        return "new"
    if target is None:
        return "removed"
    if base == "passed" and target != "passed":
        return "regression"
    if base != "passed" and target == "passed":
        return "fix"
    return "same"


@dataclass(frozen=True)
class CaseChange:
    """Status de um caso nas duas execuções comparadas e a mudança entre eles."""

    case_id: UUID | None
    case_name: str
    base_status: str | None
    target_status: str | None
    change: str


def compare(repo: EvalRunRepository, base: EvalRun, target: EvalRun) -> list[CaseChange]:
    """Caso a caso, na ordem da execução alvo e depois os que só existiam na base."""

    def keyed(run: EvalRun) -> dict[str, EvalResult]:
        # pelo id do caso; caso apagado depois da execução cai para o nome
        return {str(result.case_id or result.case_name): result for result in repo.results(run.id)}

    before, after = keyed(base), keyed(target)
    order = list(after) + [key for key in before if key not in after]
    cases = []
    for key in order:
        base_result, target_result = before.get(key), after.get(key)
        reference = target_result or base_result
        assert reference is not None
        base_status = base_result.status if base_result else None
        target_status = target_result.status if target_result else None
        cases.append(
            CaseChange(
                case_id=reference.case_id,
                case_name=reference.case_name,
                base_status=base_status,
                target_status=target_status,
                change=change(base_status, target_status),
            )
        )
    return cases


@dataclass(frozen=True)
class SuiteState:
    """Estado da suíte de um config, pela execução mais recente."""

    config_id: UUID
    # running | passing | failing | regressed
    state: str
    last_run: EvalRun
    # agendada anterior, quando a última é agendada e há com o que comparar
    previous_run_id: UUID | None
    regressions: int


def _latest_per_config(session: Session, config_ids: list[UUID] | None) -> list[EvalRun]:
    """Execução mais recente de cada config, com `DISTINCT ON` do Postgres."""
    stmt = (
        select(EvalRun)
        .distinct(EvalRun.agent_config_id)
        .order_by(EvalRun.agent_config_id, EvalRun.created_at.desc())
    )
    if config_ids is not None:
        stmt = stmt.where(EvalRun.agent_config_id.in_(config_ids))
    return list(session.scalars(stmt))


def _previous_scheduled(session: Session, run: EvalRun) -> EvalRun | None:
    """Agendada completa anterior; a que falhou no meio não serve de base para regressão."""
    stmt = (
        select(EvalRun)
        .where(
            EvalRun.agent_config_id == run.agent_config_id,
            EvalRun.trigger == "schedule",
            EvalRun.status == "completed",
            EvalRun.created_at < run.created_at,
        )
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def suite_states(session: Session, config_ids: list[UUID] | None = None) -> list[SuiteState]:
    """Estado pela execução mais recente de cada config que já rodou a suíte."""
    repo = EvalRunRepository(session)
    states: list[SuiteState] = []
    for run in _latest_per_config(session, config_ids):
        previous: EvalRun | None = None
        regressions = 0
        if run.status in ("queued", "running"):
            state = "running"
        elif run.status == "completed" and run.total > 0 and run.passed == run.total:
            state = "passing"
        else:
            state = "failing"
            # regressão só faz sentido entre execuções agendadas: mesma origem, mesmo alvo
            if run.trigger == "schedule" and run.status == "completed":
                previous = _previous_scheduled(session, run)
                if previous is not None:
                    regressions = sum(
                        1
                        for case_change in compare(repo, previous, run)
                        if case_change.change == "regression"
                    )
                    if regressions:
                        state = "regressed"
        states.append(
            SuiteState(
                config_id=run.agent_config_id,
                state=state,
                last_run=run,
                previous_run_id=previous.id if previous is not None else None,
                regressions=regressions,
            )
        )
    return states
