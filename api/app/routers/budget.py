"""Orçamento mensal por config (ADR-0021): fora da versão, como o gate da suíte."""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app import budget
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.config import AgentConfig
from app.repositories.config import ConfigRepository
from app.schemas.budget import BudgetInput, BudgetResponse

router = APIRouter(
    prefix="/api/v1/configs/{config_id}/budget",
    tags=["budget"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


def _config_or_404(session: SessionDep, config_id: UUID) -> AgentConfig:
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    return config


def _response(session: SessionDep, config: AgentConfig) -> BudgetResponse:
    period = budget.current_period()
    state = budget.state_for(config, budget.month_spend(session, config.id, period))
    return BudgetResponse(
        monthly_usd=state.limit_usd,
        alert_percent=state.alert_percent,
        hard_stop=state.hard_stop,
        period=period,
        spent_usd=state.spent_usd,
        percent=state.percent,
        level=state.level,
    )


@router.get("", response_model=BudgetResponse)
def read_budget(config_id: UUID, session: SessionDep) -> BudgetResponse:
    return _response(session, _config_or_404(session, config_id))


@router.put(
    "",
    response_model=BudgetResponse,
    dependencies=[Depends(require_scopes(Scope.CONFIGS_WRITE))],
)
def update_budget(config_id: UUID, body: BudgetInput, session: SessionDep) -> BudgetResponse:
    config = _config_or_404(session, config_id)
    config.budget_monthly_usd = (
        Decimal(str(round(body.monthly_usd, 2))) if body.monthly_usd is not None else None
    )
    config.budget_alert_percent = body.alert_percent
    config.budget_hard_stop = body.hard_stop
    session.commit()
    session.refresh(config)
    budget.forget(config.id)
    return _response(session, config)
