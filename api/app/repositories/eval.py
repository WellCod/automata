from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.eval import EvalCase


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
