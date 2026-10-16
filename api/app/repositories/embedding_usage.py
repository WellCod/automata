from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.embedders import embedding_cost
from app.models.embedding_usage import EmbeddingUsage


@dataclass
class EmbeddingTotals:
    tokens: int
    cost: float | None


def _float(v: object) -> float | None:
    return float(v) if isinstance(v, Decimal | int | float) else None


def record_embedding_usage(
    *,
    base_id: UUID,
    model: str,
    tokens: int,
    kind: str,
    agent_config_id: UUID | None = None,
) -> None:
    """Sessão própria: chamado da thread de ingestão e da tool do agente."""
    if tokens <= 0:
        return
    with Session(get_engine()) as session:
        session.add(
            EmbeddingUsage(
                base_id=base_id,
                agent_config_id=agent_config_id,
                kind=kind,
                model=model,
                period=datetime.now(UTC).strftime("%Y%m"),
                tokens=tokens,
                cost=embedding_cost(model, tokens),
            )
        )
        session.commit()


class EmbeddingUsageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def by_base(self, base_ids: list[UUID]) -> dict[UUID, EmbeddingTotals]:
        if not base_ids:
            return {}
        rows = self._session.execute(
            select(
                EmbeddingUsage.base_id,
                func.sum(EmbeddingUsage.tokens).label("tokens"),
                func.sum(EmbeddingUsage.cost).label("cost"),
            )
            .where(EmbeddingUsage.base_id.in_(base_ids))
            .group_by(EmbeddingUsage.base_id)
        ).all()
        return {
            r.base_id: EmbeddingTotals(int(r.tokens or 0), _float(r.cost))
            for r in rows
            if r.base_id is not None
        }

    def summary(self, *, since: datetime, until: datetime | None = None) -> EmbeddingTotals:
        where = [EmbeddingUsage.created_at >= since]
        if until is not None:
            where.append(EmbeddingUsage.created_at <= until)
        row = self._session.execute(
            select(
                func.sum(EmbeddingUsage.tokens).label("tokens"),
                func.sum(EmbeddingUsage.cost).label("cost"),
            ).where(*where)
        ).one()
        return EmbeddingTotals(int(row.tokens or 0), _float(row.cost))

    def by_agent(self, *, period: str, agent_config_id: UUID | None) -> dict[UUID, EmbeddingTotals]:
        stmt = (
            select(
                EmbeddingUsage.agent_config_id,
                func.sum(EmbeddingUsage.tokens).label("tokens"),
                func.sum(EmbeddingUsage.cost).label("cost"),
            )
            .where(EmbeddingUsage.period == period, EmbeddingUsage.agent_config_id.is_not(None))
            .group_by(EmbeddingUsage.agent_config_id)
        )
        if agent_config_id is not None:
            stmt = stmt.where(EmbeddingUsage.agent_config_id == agent_config_id)
        return {
            r.agent_config_id: EmbeddingTotals(int(r.tokens or 0), _float(r.cost))
            for r in self._session.execute(stmt).all()
        }
