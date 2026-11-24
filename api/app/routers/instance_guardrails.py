"""Piso de guardrails da instância (ADR-0034), só para o owner."""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.audit import note
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


def _response(floor_row: InstanceGuardrails | None) -> InstanceGuardrailsResponse:
    """Piso gravado no formato da resposta; sem linha, a instância não tem piso."""
    if floor_row is None:
        return InstanceGuardrailsResponse(settings=None)
    return InstanceGuardrailsResponse(
        settings=GuardrailSettings.model_validate(floor_row.settings),
        updated_by=floor_row.updated_by,
        updated_at=floor_row.updated_at,
    )


@router.get("", response_model=InstanceGuardrailsResponse)
def get_floor(session: SessionDep) -> InstanceGuardrailsResponse:
    """Piso atual; a tabela tem no máximo uma linha, sempre com id 1."""
    return _response(session.get(InstanceGuardrails, 1))


@router.put("", response_model=InstanceGuardrailsResponse)
def put_floor(
    body: InstanceGuardrailsInput, session: SessionDep, request: Request
) -> InstanceGuardrailsResponse:
    """Grava ou tira o piso, com o antes e o depois na trilha de auditoria."""
    actor = str(getattr(request.state, "user_id", None) or "panel")
    floor_row = session.get(InstanceGuardrails, 1)
    note(
        request,
        before=floor_row.settings if floor_row is not None else None,
        after=body.settings.model_dump(mode="json") if body.settings is not None else None,
    )
    if body.settings is None:
        if floor_row is not None:
            session.delete(floor_row)
            session.commit()
        forget()
        logger.info("piso de guardrails removido", extra={"actor": actor})
        return _response(None)
    errors = guardrail_errors(body.settings)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    floor_settings = body.settings.model_dump(mode="json")
    if floor_row is None:
        floor_row = InstanceGuardrails(id=1, settings=floor_settings, updated_by=actor)
        session.add(floor_row)
    else:
        floor_row.settings = floor_settings
        floor_row.updated_by = actor
    session.commit()
    session.refresh(floor_row)
    # o piso fica em cache por processo; sem isso o próximo run usaria o piso antigo
    forget()
    logger.info("piso de guardrails alterado", extra={"actor": actor})
    return _response(floor_row)
