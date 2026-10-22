from typing import Literal

from pydantic import BaseModel, Field


class BudgetInput(BaseModel):
    # vazio = sem orçamento
    monthly_usd: float | None = Field(default=None, gt=0, le=1_000_000)
    alert_percent: int = Field(default=80, ge=1, le=99)
    hard_stop: bool = False


class BudgetResponse(BaseModel):
    monthly_usd: float | None
    alert_percent: int
    hard_stop: bool
    # período corrente, YYYYMM, e gasto estimado nele
    period: str
    spent_usd: float
    percent: float | None
    level: Literal["ok", "warning", "exceeded"] | None
