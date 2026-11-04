"""Piso de guardrails da instância (ADR-0034), só para o owner."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.guardrails.instance import forget
from app.models.instance_guardrails import InstanceGuardrails
from app.schemas.config import GuardrailSettings
from app.services.config import guardrail_errors

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/instance-guardrails",
    tags=["instance-guardrails"],
    dependencies=[Depends(require_scopes(Scope.GUARDRAILS_ADMIN))],
)


class InstanceGuardrailsInput(BaseModel):
    # vazio tira o piso
    settings: GuardrailSettings | None


class InstanceGuardrailsResponse(BaseModel):
    settings: GuardrailSettings | None
    updated_by: str | None = None
    updated_at: datetime | None = None


def _response(row: InstanceGuardrails | None) -> InstanceGuardrailsResponse:
    if row is None:
        return InstanceGuardrailsResponse(settings=None)
    return InstanceGuardrailsResponse(
        settings=GuardrailSettings.model_validate(row.settings),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


@router.get("", response_model=InstanceGuardrailsResponse)
def get_floor(session: SessionDep) -> InstanceGuardrailsResponse:
    return _response(session.get(InstanceGuardrails, 1))


@router.put("", response_model=InstanceGuardrailsResponse)
def put_floor(
    body: InstanceGuardrailsInput, session: SessionDep, request: Request
) -> InstanceGuardrailsResponse:
    actor = str(getattr(request.state, "user_id", None) or "panel")
    row = session.get(InstanceGuardrails, 1)
    if body.settings is None:
        if row is not None:
            session.delete(row)
            session.commit()
        forget()
        logger.info("piso de guardrails removido", extra={"actor": actor})
        return _response(None)
    errors = guardrail_errors(body.settings)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    data = body.settings.model_dump(mode="json")
    if row is None:
        row = InstanceGuardrails(id=1, settings=data, updated_by=actor)
        session.add(row)
    else:
        row.settings = data
        row.updated_by = actor
    session.commit()
    session.refresh(row)
    forget()
    logger.info("piso de guardrails alterado", extra={"actor": actor})
    return _response(row)
