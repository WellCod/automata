from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.run import AgentRun


class RunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        agent_config_id: UUID,
        user_id: str,
        status: str,
        run_id: str | None = None,
        duration_ms: int | None = None,
        error: str | None = None,
    ) -> AgentRun:
        run = AgentRun(
            agent_config_id=agent_config_id,
            user_id=user_id,
            run_id=run_id,
            status=status,
            duration_ms=duration_ms,
            error=error,
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)
        return run

    def list_by_config(
        self,
        config_id: UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        base = select(AgentRun).where(AgentRun.agent_config_id == config_id)
        total: int = self._session.execute(
            select(func.count()).select_from(base.subquery())
        ).scalar_one()
        runs = (
            self._session.execute(
                base.order_by(AgentRun.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return list(runs), total
