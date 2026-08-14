from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.run import AgentRun


@dataclass
class RunMetrics:
    total_runs: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    period_days: int


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

    def metrics(self, config_id: UUID, *, period_days: int = 30) -> RunMetrics:
        since = datetime.now(UTC) - timedelta(days=period_days)
        base_filter = (
            AgentRun.agent_config_id == config_id,
            AgentRun.created_at >= since,
        )

        stats = self._session.execute(
            select(
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "error").label("errors"),
            ).where(*base_filter)
        ).one()

        total = int(stats.total)
        error_rate = int(stats.errors) / total if total > 0 else 0.0

        p50: float | None = None
        p95: float | None = None
        if total > 0:
            pct = self._session.execute(
                select(
                    func.percentile_cont(0.5).within_group(AgentRun.duration_ms).label("p50"),
                    func.percentile_cont(0.95).within_group(AgentRun.duration_ms).label("p95"),
                ).where(*base_filter, AgentRun.duration_ms.isnot(None))
            ).one()
            p50 = float(pct.p50) if pct.p50 is not None else None
            p95 = float(pct.p95) if pct.p95 is not None else None

        return RunMetrics(
            total_runs=total,
            error_rate=error_rate,
            p50_ms=p50,
            p95_ms=p95,
            period_days=period_days,
        )
