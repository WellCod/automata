from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.models.run import AgentRun
from app.models.usage import UsageEvent


@dataclass
class AgentRunSummary:
    agent_config_id: UUID
    total_runs: int
    error_count: int
    blocked_count: int = 0


@dataclass
class DailyRunStats:
    day: date
    total_runs: int
    error_count: int
    p50_ms: float | None
    p95_ms: float | None
    blocked_count: int = 0


@dataclass
class RunMetrics:
    total_runs: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    period_days: int
    # barrados por guardrail (ADR-0013): contam no total, não na taxa de erro
    blocked_runs: int = 0


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
        session_id: str | None = None,
        pending_tools: list[dict[str, Any]] | None = None,
        blocked_by: str | None = None,
        block_detail: dict[str, Any] | None = None,
        parent_run_id: str | None = None,
        eval_run_id: UUID | None = None,
    ) -> AgentRun:
        run = AgentRun(
            agent_config_id=agent_config_id,
            user_id=user_id,
            run_id=run_id,
            status=status,
            duration_ms=duration_ms,
            error=error,
            session_id=session_id,
            pending_tools=pending_tools,
            blocked_by=blocked_by,
            block_detail=block_detail,
            parent_run_id=parent_run_id,
            eval_run_id=eval_run_id,
        )
        self._session.add(run)
        self._session.flush()
        return run

    def upsert(
        self,
        *,
        agent_config_id: UUID,
        user_id: str,
        status: str,
        run_id: str | None = None,
        duration_ms: int | None = None,
        error: str | None = None,
        session_id: str | None = None,
        pending_tools: list[dict[str, Any]] | None = None,
        blocked_by: str | None = None,
        block_detail: dict[str, Any] | None = None,
        parent_run_id: str | None = None,
        eval_run_id: UUID | None = None,
    ) -> AgentRun:
        """Atualiza o run de mesmo run_id (pausado e retomado) ou cria um novo."""
        existing = None
        if run_id is not None:
            existing = self._session.scalars(
                select(AgentRun).where(
                    AgentRun.run_id == run_id, AgentRun.agent_config_id == agent_config_id
                )
            ).first()
        if existing is None:
            return self.record(
                agent_config_id=agent_config_id,
                user_id=user_id,
                run_id=run_id,
                status=status,
                duration_ms=duration_ms,
                error=error,
                session_id=session_id,
                pending_tools=pending_tools,
                blocked_by=blocked_by,
                block_detail=block_detail,
                parent_run_id=parent_run_id,
                eval_run_id=eval_run_id,
            )
        existing.status = status
        existing.error = error
        existing.pending_tools = pending_tools
        existing.blocked_by = blocked_by
        existing.block_detail = block_detail
        existing.session_id = session_id or existing.session_id
        if duration_ms is not None:
            existing.duration_ms = (existing.duration_ms or 0) + duration_ms
        self._session.flush()
        return existing

    def child_consumption(self, run_ids: list[str]) -> dict[str, tuple[int, int, float | None]]:
        """run do workflow -> (etapas, tokens, custo), somando as etapas filhas."""
        if not run_ids:
            return {}
        children = (
            select(
                AgentRun.parent_run_id.label("parent"),
                func.count(AgentRun.id).label("steps"),
            )
            .where(AgentRun.parent_run_id.in_(run_ids))
            .group_by(AgentRun.parent_run_id)
        )
        usage = (
            select(
                AgentRun.parent_run_id.label("parent"),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0).label("tokens"),
                func.sum(UsageEvent.cost).label("cost"),
            )
            .join(UsageEvent, UsageEvent.run_id == AgentRun.run_id)
            .where(AgentRun.parent_run_id.in_(run_ids))
            .group_by(AgentRun.parent_run_id)
        )
        totals = {
            r.parent: (int(r.tokens), float(r.cost) if r.cost is not None else None)
            for r in self._session.execute(usage)
        }
        return {
            r.parent: (int(r.steps), *totals.get(r.parent, (0, None)))
            for r in self._session.execute(children)
        }

    def list_paused(self, config_ids: list[UUID] | None = None) -> list[AgentRun]:
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.status == "paused",
                AgentRun.pending_tools.is_not(None),
                AgentRun.eval_run_id.is_(None),
            )
            .order_by(AgentRun.created_at.desc())
        )
        if config_ids is not None:
            stmt = stmt.where(AgentRun.agent_config_id.in_(config_ids))
        return list(self._session.scalars(stmt))

    def list_by_config(
        self,
        config_id: UUID,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AgentRun], int]:
        base = select(AgentRun).where(
            AgentRun.agent_config_id == config_id, AgentRun.eval_run_id.is_(None)
        )
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

    def metrics(
        self,
        config_id: UUID,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        period_days: int = 30,
    ) -> RunMetrics:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=period_days)
        base_filter = [
            AgentRun.agent_config_id == config_id,
            AgentRun.created_at >= since,
            AgentRun.eval_run_id.is_(None),
        ]
        if until is not None:
            base_filter.append(AgentRun.created_at <= until)

        stats = self._session.execute(
            select(
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "error").label("errors"),
                func.count(AgentRun.id).filter(AgentRun.status == "blocked").label("blocked"),
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
            blocked_runs=int(stats.blocked),
            p50_ms=p50,
            p95_ms=p95,
            period_days=period_days,
        )

    def runs_by_agent(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        period_days: int = 30,
    ) -> list[AgentRunSummary]:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=period_days)
        where_clauses = [AgentRun.created_at >= since, AgentRun.eval_run_id.is_(None)]
        if until is not None:
            where_clauses.append(AgentRun.created_at <= until)
        rows = self._session.execute(
            select(
                AgentRun.agent_config_id,
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "error").label("errors"),
                func.count(AgentRun.id).filter(AgentRun.status == "blocked").label("blocked"),
            )
            .where(*where_clauses)
            .group_by(AgentRun.agent_config_id)
            .order_by(func.count(AgentRun.id).desc())
        ).all()
        return [
            AgentRunSummary(
                agent_config_id=r.agent_config_id,
                total_runs=int(r.total),
                error_count=int(r.errors),
                blocked_count=int(r.blocked),
            )
            for r in rows
        ]

    def metrics_global(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        period_days: int = 30,
    ) -> RunMetrics:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=period_days)
        where_clauses = [AgentRun.created_at >= since, AgentRun.eval_run_id.is_(None)]
        if until is not None:
            where_clauses.append(AgentRun.created_at <= until)

        stats = self._session.execute(
            select(
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "error").label("errors"),
                func.count(AgentRun.id).filter(AgentRun.status == "blocked").label("blocked"),
            ).where(*where_clauses)
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
                ).where(*where_clauses, AgentRun.duration_ms.isnot(None))
            ).one()
            p50 = float(pct.p50) if pct.p50 is not None else None
            p95 = float(pct.p95) if pct.p95 is not None else None

        return RunMetrics(
            total_runs=total,
            error_rate=error_rate,
            blocked_runs=int(stats.blocked),
            p50_ms=p50,
            p95_ms=p95,
            period_days=period_days,
        )

    def daily(
        self,
        *,
        since: datetime,
        until: datetime | None = None,
        config_id: UUID | None = None,
    ) -> list[DailyRunStats]:
        """Runs por dia (UTC); dias sem run não aparecem."""
        day = cast(func.timezone("UTC", AgentRun.created_at), Date).label("day")
        where_clauses = [AgentRun.created_at >= since, AgentRun.eval_run_id.is_(None)]
        if until is not None:
            where_clauses.append(AgentRun.created_at <= until)
        if config_id is not None:
            where_clauses.append(AgentRun.agent_config_id == config_id)
        rows = self._session.execute(
            select(
                day,
                func.count(AgentRun.id).label("total"),
                func.count(AgentRun.id).filter(AgentRun.status == "error").label("errors"),
                func.count(AgentRun.id).filter(AgentRun.status == "blocked").label("blocked"),
                func.percentile_cont(0.5).within_group(AgentRun.duration_ms).label("p50"),
                func.percentile_cont(0.95).within_group(AgentRun.duration_ms).label("p95"),
            )
            .where(*where_clauses)
            .group_by(day)
            .order_by(day)
        ).all()
        return [
            DailyRunStats(
                day=r.day,
                total_runs=int(r.total),
                error_count=int(r.errors),
                blocked_count=int(r.blocked),
                p50_ms=float(r.p50) if r.p50 is not None else None,
                p95_ms=float(r.p95) if r.p95 is not None else None,
            )
            for r in rows
        ]

    def blocked_by_rule(
        self,
        *,
        since: datetime,
        until: datetime | None = None,
        config_id: UUID | None = None,
    ) -> dict[str, int]:
        where = [
            AgentRun.status == "blocked",
            AgentRun.created_at >= since,
            AgentRun.eval_run_id.is_(None),
        ]
        if until is not None:
            where.append(AgentRun.created_at <= until)
        if config_id is not None:
            where.append(AgentRun.agent_config_id == config_id)
        rows = self._session.execute(
            select(AgentRun.blocked_by, func.count(AgentRun.id))
            .where(*where)
            .group_by(AgentRun.blocked_by)
        ).all()
        return {str(rule or "desconhecido"): int(n) for rule, n in rows}
