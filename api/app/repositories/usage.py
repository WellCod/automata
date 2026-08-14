from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usage import UsageEvent


@dataclass
class UsageSummary:
    total_tokens: int
    total_cost: float | None


@dataclass
class AgentUsageSummary:
    agent_config_id: UUID
    total_tokens: int
    total_cost: float | None


@dataclass
class UsageRollup:
    agent_config_id: UUID
    period: str
    run_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float | None


class UsageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record_event(
        self,
        *,
        agent_config_id: UUID,
        user_id: str,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        run_id: str | None = None,
        cost: float | None = None,
        period: str | None = None,
    ) -> UsageEvent:
        if period is None:
            period = datetime.now(UTC).strftime("%Y%m")
        event = UsageEvent(
            agent_config_id=agent_config_id,
            user_id=user_id,
            run_id=run_id,
            model_id=model_id,
            period=period,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=cost,
        )
        self._session.add(event)
        self._session.commit()
        self._session.refresh(event)
        return event

    def usage_summary(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        period_days: int = 30,
    ) -> UsageSummary:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=period_days)
        where_clauses = [UsageEvent.created_at >= since]
        if until is not None:
            where_clauses.append(UsageEvent.created_at <= until)
        row = self._session.execute(
            select(
                func.sum(UsageEvent.total_tokens).label("tokens"),
                func.sum(UsageEvent.cost).label("cost"),
            ).where(*where_clauses)
        ).one()
        cost = float(row.cost) if isinstance(row.cost, Decimal) else row.cost
        return UsageSummary(
            total_tokens=int(row.tokens or 0),
            total_cost=cost,
        )

    def usage_by_agent(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        period_days: int = 30,
    ) -> list[AgentUsageSummary]:
        if since is None:
            since = datetime.now(UTC) - timedelta(days=period_days)
        where_clauses = [UsageEvent.created_at >= since]
        if until is not None:
            where_clauses.append(UsageEvent.created_at <= until)
        rows = self._session.execute(
            select(
                UsageEvent.agent_config_id,
                func.sum(UsageEvent.total_tokens).label("tokens"),
                func.sum(UsageEvent.cost).label("cost"),
            )
            .where(*where_clauses)
            .group_by(UsageEvent.agent_config_id)
        ).all()
        return [
            AgentUsageSummary(
                agent_config_id=r.agent_config_id,
                total_tokens=int(r.tokens or 0),
                total_cost=float(r.cost) if isinstance(r.cost, Decimal) else r.cost,
            )
            for r in rows
        ]

    def rollup(
        self,
        *,
        period: str,
        agent_config_id: UUID | None = None,
    ) -> list[UsageRollup]:
        stmt = select(
            UsageEvent.agent_config_id,
            UsageEvent.period,
            func.count(UsageEvent.id).label("run_count"),
            func.sum(UsageEvent.input_tokens).label("input_tokens"),
            func.sum(UsageEvent.output_tokens).label("output_tokens"),
            func.sum(UsageEvent.total_tokens).label("total_tokens"),
            func.sum(UsageEvent.cost).label("cost"),
        ).where(UsageEvent.period == period)

        if agent_config_id is not None:
            stmt = stmt.where(UsageEvent.agent_config_id == agent_config_id)

        stmt = stmt.group_by(UsageEvent.agent_config_id, UsageEvent.period)

        rows = self._session.execute(stmt).all()
        return [
            UsageRollup(
                agent_config_id=row.agent_config_id,
                period=row.period,
                run_count=row.run_count,
                input_tokens=int(row.input_tokens or 0),
                output_tokens=int(row.output_tokens or 0),
                total_tokens=int(row.total_tokens or 0),
                cost=float(row.cost) if isinstance(row.cost, Decimal) else row.cost,
            )
            for row in rows
        ]
