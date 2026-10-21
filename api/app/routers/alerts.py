"""Destinos de aviso da instância (ADR-0021): só owner, como emitir token de integração."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.evals import webhook
from app.mcp.egress import EgressDenied
from app.models.alert import AlertDestination
from app.schemas.alert import (
    AlertDestinationCreate,
    AlertDestinationIssued,
    AlertDestinationResponse,
    AlertDestinationUpdate,
    AlertEvent,
    AlertTestResult,
)
from app.secrets import SecretsKeyMissing

router = APIRouter(
    prefix="/api/v1/alert-destinations",
    tags=["alerts"],
    dependencies=[Depends(require_scopes(Scope.INTEGRATIONS_WRITE))],
)


def _response(d: AlertDestination) -> dict[str, Any]:
    return {
        "id": d.id,
        "name": d.name,
        "host": d.webhook_host,
        "events": cast(list[AlertEvent], d.events),
        "created_by": d.created_by,
        "last_status": d.last_status,
        "last_at": d.last_at,
        "created_at": d.created_at,
    }


def _or_404(session: SessionDep, destination_id: UUID) -> AlertDestination:
    found = session.get(AlertDestination, destination_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Destino não encontrado")
    return found


def _unique(events: list[AlertEvent]) -> list[str]:
    return list(dict.fromkeys(events))


@router.get("", response_model=list[AlertDestinationResponse])
def list_destinations(session: SessionDep) -> list[AlertDestinationResponse]:
    rows = session.scalars(select(AlertDestination).order_by(AlertDestination.created_at))
    return [AlertDestinationResponse(**_response(d)) for d in rows]


@router.post("", response_model=AlertDestinationIssued, status_code=201)
def create_destination(
    body: AlertDestinationCreate, request: Request, session: SessionDep
) -> AlertDestinationIssued:
    """Cadastra o destino; o segredo é devolvido uma vez só."""
    try:
        encrypted, host, secret = webhook.seal(body.url)
    except (EgressDenied, SecretsKeyMissing) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dest = AlertDestination(
        name=body.name,
        webhook_encrypted=encrypted,
        webhook_host=host,
        events=_unique(body.events),
        created_by=str(getattr(request.state, "user_id", None) or "panel"),
    )
    session.add(dest)
    session.commit()
    session.refresh(dest)
    return AlertDestinationIssued(**_response(dest), secret=secret)


@router.put("/{destination_id}", response_model=AlertDestinationResponse)
def update_destination(
    destination_id: UUID, body: AlertDestinationUpdate, session: SessionDep
) -> AlertDestinationResponse:
    dest = _or_404(session, destination_id)
    dest.name = body.name
    dest.events = _unique(body.events)
    session.commit()
    session.refresh(dest)
    return AlertDestinationResponse(**_response(dest))


@router.delete("/{destination_id}", status_code=204)
def delete_destination(destination_id: UUID, session: SessionDep) -> Response:
    session.delete(_or_404(session, destination_id))
    session.commit()
    return Response(status_code=204)


@router.post("/{destination_id}/test", response_model=AlertTestResult)
def test_destination(destination_id: UUID, session: SessionDep) -> AlertTestResult:
    """Manda um alert.test, uma tentativa só, para conferir a integração."""
    dest = _or_404(session, destination_id)
    try:
        target = webhook.unseal(dest.webhook_encrypted)
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body = webhook.body_for(
        "alert.test",
        {"destination": dest.name},
        f"Teste do destino de aviso {dest.name}: o webhook está funcionando.",
    )
    status = webhook.deliver(target, "alert.test", body, attempts=1)
    dest.last_status = status
    dest.last_at = datetime.now(UTC)
    session.commit()
    return AlertTestResult(status=status, delivered=status.startswith("HTTP 2"))
