"""Destinos de aviso da instância (ADR-0021): só owner, como emitir token de integração."""

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select

from app import mailer
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.evals import webhook
from app.mcp.egress import EgressDenied
from app.models.alert import AlertDestination
from app.repositories.user import emails_by_id
from app.schemas.alert import (
    AlertChannels,
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


def _response(
    destination: AlertDestination, emails: dict[str, str] | None = None
) -> dict[str, Any]:
    """Campos comuns às respostas do destino; o segredo do webhook nunca sai daqui."""
    return {
        "id": destination.id,
        "name": destination.name,
        "kind": destination.kind,
        "host": destination.webhook_host,
        "emails": list(destination.email_to or []),
        "events": cast(list[AlertEvent], destination.events),
        # e-mail de quem criou, quando é usuário do painel (Fase 44)
        "created_by": (emails or {}).get(destination.created_by, destination.created_by),
        "last_status": destination.last_status,
        "last_at": destination.last_at,
        "created_at": destination.created_at,
    }


def _or_404(session: SessionDep, destination_id: UUID) -> AlertDestination:
    found = session.get(AlertDestination, destination_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Destino não encontrado")
    return found


def _unique(events: list[AlertEvent]) -> list[str]:
    """Tira eventos repetidos mantendo a ordem em que vieram."""
    return list(dict.fromkeys(events))


@router.get("/channels", response_model=AlertChannels)
def channels() -> AlertChannels:
    """Canais disponíveis na instância: e-mail só aparece com SMTP configurado."""
    return AlertChannels(email=mailer.configured())


@router.get("", response_model=list[AlertDestinationResponse])
def list_destinations(session: SessionDep) -> list[AlertDestinationResponse]:
    rows = session.scalars(select(AlertDestination).order_by(AlertDestination.created_at)).all()
    emails = emails_by_id(session, {destination.created_by for destination in rows})
    return [AlertDestinationResponse(**_response(destination, emails)) for destination in rows]


@router.post("", response_model=AlertDestinationIssued, status_code=201)
def create_destination(
    body: AlertDestinationCreate, request: Request, session: SessionDep
) -> AlertDestinationIssued:
    """Cadastra o destino; o segredo do webhook é devolvido uma vez só."""
    actor = str(getattr(request.state, "user_id", None) or "panel")
    if body.kind == "email":
        if not mailer.configured():
            raise HTTPException(status_code=422, detail="SMTP_HOST não configurado na API")
        destination = AlertDestination(
            name=body.name,
            kind="email",
            webhook_encrypted=None,
            webhook_host="e-mail",
            email_to=list(dict.fromkeys(str(email).lower() for email in body.emails)),
            events=_unique(body.events),
            created_by=actor,
        )
        session.add(destination)
        session.commit()
        session.refresh(destination)
        return AlertDestinationIssued(**_response(destination), secret="")
    try:
        encrypted, host, secret = webhook.seal(body.url or "")
    except (EgressDenied, SecretsKeyMissing) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    destination = AlertDestination(
        name=body.name,
        webhook_encrypted=encrypted,
        webhook_host=host,
        events=_unique(body.events),
        created_by=actor,
    )
    session.add(destination)
    session.commit()
    session.refresh(destination)
    return AlertDestinationIssued(**_response(destination), secret=secret)


@router.put("/{destination_id}", response_model=AlertDestinationResponse)
def update_destination(
    destination_id: UUID, body: AlertDestinationUpdate, session: SessionDep
) -> AlertDestinationResponse:
    destination = _or_404(session, destination_id)
    destination.name = body.name
    destination.events = _unique(body.events)
    session.commit()
    session.refresh(destination)
    return AlertDestinationResponse(**_response(destination))


@router.delete("/{destination_id}", status_code=204)
def delete_destination(destination_id: UUID, session: SessionDep) -> Response:
    session.delete(_or_404(session, destination_id))
    session.commit()
    return Response(status_code=204)


@router.post("/{destination_id}/test", response_model=AlertTestResult)
def test_destination(destination_id: UUID, session: SessionDep) -> AlertTestResult:
    """Manda um alert.test, uma tentativa só, para conferir a integração."""
    destination = _or_404(session, destination_id)
    if destination.kind == "email":
        status = mailer.send(
            list(destination.email_to or []),
            "[Automata] teste do destino de aviso",
            f"Teste do destino de aviso {destination.name}: o e-mail está funcionando.",
        )
        destination.last_status = status
        destination.last_at = datetime.now(UTC)
        session.commit()
        return AlertTestResult(status=status, delivered=status == mailer.SENT)
    try:
        target = webhook.unseal(destination.webhook_encrypted or "")
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body = webhook.body_for(
        "alert.test",
        {"destination": destination.name},
        f"Teste do destino de aviso {destination.name}: o webhook está funcionando.",
    )
    status = webhook.deliver(target, "alert.test", body, attempts=1)
    destination.last_status = status
    destination.last_at = datetime.now(UTC)
    session.commit()
    return AlertTestResult(status=status, delivered=status.startswith("HTTP 2"))
