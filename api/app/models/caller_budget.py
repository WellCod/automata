from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.config import Base


class CallerBudget(Base):
    """Orçamento mensal de quem chama (ADR-0031), em todos os agentes da instância."""

    __tablename__ = "caller_budget"

    # id do usuário do painel ou integration:<id> do token, como no usage_event
    subject: Mapped[str] = mapped_column(String(255), primary_key=True)
    monthly_usd: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    warn_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    hard_stop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # último período (AAAAMM) em que cada aviso saiu: um de cada por mês
    warned_period: Mapped[str | None] = mapped_column(String(6), nullable=True)
    exceeded_period: Mapped[str | None] = mapped_column(String(6), nullable=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
