"""Cadastro dos canais de conversa (ADR-0044). Só owner: a credencial fala pela empresa."""

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.authz import Scope, require_scopes
from app.channels import providers
from app.db import SessionDep
from app.models.channel import DEFAULT_HANDOFF_KEYWORDS, DEFAULT_HANDOFF_MESSAGE, Channel
from app.models.config import AgentConfig
from app.secrets import SecretsKeyMissing, decrypt_json, encrypt_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/channels",
    tags=["channels"],
    dependencies=[Depends(require_scopes(Scope.CHANNELS_ADMIN))],
)

Kind = Literal["whatsapp", "slack"]


def _keywords(v: list[str]) -> list[str]:
    cleaned = [k.strip().lower() for k in v if k.strip()]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError("palavra repetida")
    return cleaned


class ChannelInput(BaseModel):
    kind: Kind
    name: str = Field(min_length=1, max_length=80)
    config_id: UUID
    credentials: dict[str, str]
    enabled: bool = True
    handoff_enabled: bool = True
    handoff_keywords: list[str] = Field(
        default_factory=lambda: list(DEFAULT_HANDOFF_KEYWORDS), max_length=10
    )
    handoff_message: str = Field(default=DEFAULT_HANDOFF_MESSAGE, min_length=1, max_length=500)

    _kw = field_validator("handoff_keywords")(_keywords)


class ChannelUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    config_id: UUID
    enabled: bool
    handoff_enabled: bool
    handoff_keywords: list[str] = Field(max_length=10)
    handoff_message: str = Field(min_length=1, max_length=500)
    # vazio mantém a credencial atual; preenchido troca os campos enviados
    credentials: dict[str, str] | None = None

    _kw = field_validator("handoff_keywords")(_keywords)


class ChannelResponse(BaseModel):
    id: UUID
    kind: str
    name: str
    config_id: UUID
    config_name: str | None
    enabled: bool
    handoff_enabled: bool
    handoff_keywords: list[str]
    handoff_message: str
    # caminho que o provedor chama; a credencial nunca volta
    webhook_path: str
    credential_fields: list[str]
    created_at: datetime


class ChannelTest(BaseModel):
    ok: bool
    detail: str


def _response(channel: Channel, config_name: str | None) -> ChannelResponse:
    return ChannelResponse(
        id=channel.id,
        kind=channel.kind,
        name=channel.name,
        config_id=channel.config_id,
        config_name=config_name,
        enabled=channel.enabled,
        handoff_enabled=channel.handoff_enabled,
        handoff_keywords=list(channel.handoff_keywords),
        handoff_message=channel.handoff_message,
        webhook_path=f"/hooks/channels/{channel.id}",
        credential_fields=sorted(decrypt_json(channel.credentials_encrypted)),
        created_at=channel.created_at,
    )


def _check_credentials(kind: str, creds: dict[str, str]) -> dict[str, str]:
    needed = providers.CREDENTIAL_FIELDS[kind]
    cleaned = {k: v.strip() for k, v in creds.items() if k in needed and v.strip()}
    missing = [k for k in needed if k not in cleaned]
    if missing:
        raise HTTPException(status_code=422, detail=f"Faltam na credencial: {', '.join(missing)}")
    if any(len(v) > 2000 for v in cleaned.values()):
        raise HTTPException(status_code=422, detail="Credencial grande demais")
    return cleaned


def _seal(creds: dict[str, str]) -> str:
    try:
        return encrypt_json(creds)
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _config_or_422(session: SessionDep, config_id: UUID) -> AgentConfig:
    config = session.get(AgentConfig, config_id)
    if config is None or config.kind not in ("agent", "team"):
        raise HTTPException(status_code=422, detail="Escolha um agente ou time")
    if config.current_version_id is None:
        raise HTTPException(status_code=422, detail="Publique o agente antes de ligar um canal")
    return config


def _channel_or_404(session: SessionDep, channel_id: UUID) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    return channel


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


@router.get("", response_model=list[ChannelResponse])
def list_channels(session: SessionDep) -> list[ChannelResponse]:
    rows = session.execute(
        select(Channel, AgentConfig.name)
        .join(AgentConfig, AgentConfig.id == Channel.config_id)
        .order_by(Channel.created_at)
    ).all()
    return [_response(channel, name) for channel, name in rows]


@router.post("", response_model=ChannelResponse, status_code=201)
def create_channel(body: ChannelInput, request: Request, session: SessionDep) -> ChannelResponse:
    config = _config_or_422(session, body.config_id)
    creds = _check_credentials(body.kind, body.credentials)
    channel = Channel(
        kind=body.kind,
        name=body.name.strip(),
        config_id=config.id,
        enabled=body.enabled,
        credentials_encrypted=_seal(creds),
        handoff_enabled=body.handoff_enabled,
        handoff_keywords=body.handoff_keywords,
        handoff_message=body.handoff_message,
        created_by=_actor(request),
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _response(channel, config.name)


@router.put("/{channel_id}", response_model=ChannelResponse)
def update_channel(channel_id: UUID, body: ChannelUpdate, session: SessionDep) -> ChannelResponse:
    channel = _channel_or_404(session, channel_id)
    config = _config_or_422(session, body.config_id)
    if body.credentials:
        merged = {**decrypt_json(channel.credentials_encrypted), **body.credentials}
        channel.credentials_encrypted = _seal(_check_credentials(channel.kind, merged))
    channel.name = body.name.strip()
    channel.config_id = config.id
    channel.enabled = body.enabled
    channel.handoff_enabled = body.handoff_enabled
    channel.handoff_keywords = body.handoff_keywords
    channel.handoff_message = body.handoff_message
    session.commit()
    session.refresh(channel)
    return _response(channel, config.name)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: UUID, session: SessionDep) -> Response:
    session.delete(_channel_or_404(session, channel_id))
    session.commit()
    return Response(status_code=204)


@router.post("/{channel_id}/test", response_model=ChannelTest)
def test_channel(channel_id: UUID, session: SessionDep) -> ChannelTest:
    """Confere a credencial no provedor sem mandar mensagem a ninguém."""
    channel = _channel_or_404(session, channel_id)
    creds = decrypt_json(channel.credentials_encrypted)
    try:
        with providers._http() as client:
            if channel.kind == "whatsapp":
                resp = client.get(
                    f"{providers.GRAPH_URL}/{creds['phone_number_id']}",
                    params={"fields": "display_phone_number"},
                    headers={"Authorization": f"Bearer {creds['access_token']}"},
                )
                if resp.status_code != 200:
                    return ChannelTest(ok=False, detail=f"Meta recusou ({resp.status_code})")
                number = resp.json().get("display_phone_number", "")
                return ChannelTest(ok=True, detail=f"Número {number}".strip())
            resp = client.post(
                f"{providers.SLACK_URL}/auth.test",
                headers={"Authorization": f"Bearer {creds['bot_token']}"},
            )
            data = resp.json() if resp.status_code < 500 else {}
            if not data.get("ok"):
                return ChannelTest(
                    ok=False, detail=f"Slack recusou: {data.get('error', resp.status_code)}"
                )
            return ChannelTest(ok=True, detail=f"Workspace {data.get('team', '')}".strip())
    except (httpx.HTTPError, ValueError) as exc:
        return ChannelTest(ok=False, detail=f"Sem resposta do provedor: {exc.__class__.__name__}")
