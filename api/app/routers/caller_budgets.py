"""Orçamento mensal por quem chama (ADR-0031), só para o owner."""

import contextlib
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz import Scope, require_scopes
from app.budget import current_period
from app.caller_budget import forget, month_spend, state_for
from app.db import SessionDep
from app.models.caller_budget import CallerBudget
from app.models.integration import IntegrationToken
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/caller-budgets",
    tags=["caller-budgets"],
    dependencies=[Depends(require_scopes(Scope.BUDGETS_ADMIN))],
)

_INTEGRATION = "integration:"


class CallerBudgetInput(BaseModel):
    monthly_usd: float = Field(gt=0, le=1_000_000)
    warn_percent: int = Field(default=80, ge=1, le=100)
    hard_stop: bool = False


class CallerBudgetResponse(BaseModel):
    subject: str
    # e-mail do usuário ou nome do token de integração
    label: str
    kind: str  # user, integration
    monthly_usd: float
    warn_percent: int
    hard_stop: bool
    spent_usd: float
    percent: float
    level: str
    updated_at: datetime


def _label(session: Session, subject: str) -> tuple[str, str] | None:
    """Nome e tipo de quem chama; None quando o sujeito não existe na instância."""
    if subject.startswith(_INTEGRATION):
        with contextlib.suppress(ValueError):
            token = session.get(IntegrationToken, UUID(subject.removeprefix(_INTEGRATION)))
            if token is not None:
                return token.name, "integration"
        return None
    with contextlib.suppress(ValueError):
        user = session.get(User, UUID(subject))
        if user is not None:
            return user.email, "user"
    return None


def _response(session: Session, budget: CallerBudget) -> CallerBudgetResponse:
    label, kind = _label(session, budget.subject) or (budget.subject, "removido")
    state = state_for(budget, month_spend(session, budget.subject, current_period()))
    return CallerBudgetResponse(
        subject=budget.subject,
        label=label,
        kind=kind,
        monthly_usd=float(budget.monthly_usd),
        warn_percent=budget.warn_percent,
        hard_stop=budget.hard_stop,
        spent_usd=round(state.spent_usd, 4),
        percent=round(state.percent, 1),
        level=state.level,
        updated_at=budget.updated_at,
    )


@router.get("", response_model=list[CallerBudgetResponse])
def list_budgets(session: SessionDep) -> list[CallerBudgetResponse]:
    budgets = session.scalars(select(CallerBudget).order_by(CallerBudget.subject)).all()
    return [_response(session, b) for b in budgets]


@router.put("/{subject}", response_model=CallerBudgetResponse)
def put_budget(
    subject: str, body: CallerBudgetInput, session: SessionDep, request: Request
) -> CallerBudgetResponse:
    if _label(session, subject) is None:
        raise HTTPException(status_code=404, detail="Usuário ou token de integração não encontrado")
    budget = session.get(CallerBudget, subject)
    if budget is None:
        budget = CallerBudget(subject=subject, updated_by="")
        session.add(budget)
    budget.monthly_usd = Decimal(str(body.monthly_usd))
    budget.warn_percent = body.warn_percent
    budget.hard_stop = body.hard_stop
    budget.updated_by = str(getattr(request.state, "user_id", None) or "panel")
    session.commit()
    session.refresh(budget)
    forget(subject)
    return _response(session, budget)


@router.delete("/{subject}", status_code=204)
def delete_budget(subject: str, session: SessionDep) -> None:
    budget = session.get(CallerBudget, subject)
    if budget is None:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    session.delete(budget)
    session.commit()
    forget(subject)
