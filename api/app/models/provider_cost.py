from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class ProviderCost(Base):
    """Custo do dia informado pelo relatório do provedor (ADR-0037), para conferir o estimado."""

    __tablename__ = "provider_cost"

    provider: Mapped[str] = mapped_column(String(16), primary_key=True)  # anthropic, openai
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    reported_usd: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # aviso de divergência do dia; um por provedor e dia
    alerted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
