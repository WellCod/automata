from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.eval import EvalCase, EvalResult, EvalRun, EvalSchedule


class EvalCaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_by_config(self, config_id: UUID) -> list[EvalCase]:
        stmt = (
            select(EvalCase)
            .where(EvalCase.agent_config_id == config_id)
            .order_by(EvalCase.position, EvalCase.created_at)
        )
        return list(self._session.scalars(stmt))

    def get(self, config_id: UUID, case_id: UUID) -> EvalCase | None:
        case = self._session.get(EvalCase, case_id)
        return case if case is not None and case.agent_config_id == config_id else None

    def count(self, config_id: UUID) -> int:
        stmt = (
            select(func.count()).select_from(EvalCase).where(EvalCase.agent_config_id == config_id)
        )
        return int(self._session.scalar(stmt) or 0)

    def name_taken(self, config_id: UUID, name: str, exclude: UUID | None = None) -> bool:
        stmt = select(EvalCase.id).where(
            EvalCase.agent_config_id == config_id, EvalCase.name == name
        )
        if exclude is not None:
            stmt = stmt.where(EvalCase.id != exclude)
        return self._session.scalars(stmt).first() is not None

    def next_position(self, config_id: UUID) -> int:
        stmt = select(func.max(EvalCase.position)).where(EvalCase.agent_config_id == config_id)
        current = self._session.scalar(stmt)
        return 0 if current is None else int(current) + 1

    def add(self, case: EvalCase) -> EvalCase:
        self._session.add(case)
        self._session.flush()
        return case

    def delete(self, case: EvalCase) -> None:
        self._session.delete(case)
        self._session.flush()


class EvalRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: EvalRun) -> EvalRun:
        self._session.add(run)
        self._session.flush()
        return run

    def get(self, config_id: UUID, run_id: UUID) -> EvalRun | None:
        run = self._session.get(EvalRun, run_id)
        return run if run is not None and run.agent_config_id == config_id else None

    def active(self, config_id: UUID) -> EvalRun | None:
        stmt = select(EvalRun).where(
            EvalRun.agent_config_id == config_id, EvalRun.status.in_(("queued", "running"))
        )
        return self._session.scalars(stmt).first()

    def list_by_config(self, config_id: UUID, limit: int = 20) -> list[EvalRun]:
        stmt = (
            select(EvalRun)
            .where(EvalRun.agent_config_id == config_id)
            .order_by(EvalRun.created_at.desc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def results(self, run_id: UUID) -> list[EvalResult]:
        stmt = (
            select(EvalResult).where(EvalResult.eval_run_id == run_id).order_by(EvalResult.position)
        )
        return list(self._session.scalars(stmt))


class EvalScheduleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, config_id: UUID) -> EvalSchedule | None:
        stmt = select(EvalSchedule).where(EvalSchedule.agent_config_id == config_id)
        return self._session.scalars(stmt).first()

    def add(self, schedule: EvalSchedule) -> EvalSchedule:
        self._session.add(schedule)
        self._session.flush()
        return schedule

    def delete(self, schedule: EvalSchedule) -> None:
        self._session.delete(schedule)

    def claim_due(self, now: datetime, limit: int = 10) -> list[EvalSchedule]:
        """Agendamentos vencidos, travados até o commit; outra réplica pula os travados."""
        stmt = (
            select(EvalSchedule)
            .where(EvalSchedule.enabled.is_(True), EvalSchedule.next_run_at <= now)
            .order_by(EvalSchedule.next_run_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(self._session.scalars(stmt))
