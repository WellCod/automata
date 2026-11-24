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
from app.models.channel import (
    DEFAULT_EXIT_KEYWORDS,
    DEFAULT_HANDOFF_KEYWORDS,
    DEFAULT_HANDOFF_MESSAGE,
    DEFAULT_WELCOME_MESSAGE,
    Channel,
)
from app.models.config import AgentConfig
from app.secrets import SecretsKeyMissing, decrypt_json, encrypt_json

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/channels",
    tags=["channels"],
    dependencies=[Depends(require_scopes(Scope.CHANNELS_ADMIN))],
)

Kind = Literal["whatsapp", "slack"]


def _keywords(keywords: list[str]) -> list[str]:
    """Normaliza as palavras-chave (sem espaço, minúsculas) e recusa repetidas."""
    cleaned = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
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
    welcome_message: str = Field(default=DEFAULT_WELCOME_MESSAGE, max_length=1000)
    exit_keywords: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXIT_KEYWORDS), max_length=10
    )

    _kw = field_validator("handoff_keywords", "exit_keywords")(_keywords)


class ChannelUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    config_id: UUID
    enabled: bool
    handoff_enabled: bool
    handoff_keywords: list[str] = Field(max_length=10)
    handoff_message: str = Field(min_length=1, max_length=500)
    welcome_message: str = Field(default=DEFAULT_WELCOME_MESSAGE, max_length=1000)
    exit_keywords: list[str] = Field(
        default_factory=lambda: list(DEFAULT_EXIT_KEYWORDS), max_length=10
    )
    # vazio mantém a credencial atual; preenchido troca os campos enviados
    credentials: dict[str, str] | None = None

    _kw = field_validator("handoff_keywords", "exit_keywords")(_keywords)


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
    welcome_message: str
    exit_keywords: list[str]
    # avisos sobre o agente ligado (ex.: tool com confirmação, que no canal vira atendente)
    warnings: list[str] = []
    # caminho que o provedor chama; a credencial nunca volta
    webhook_path: str
    credential_fields: list[str]
    created_at: datetime


class ChannelTest(BaseModel):
    ok: bool
    detail: str


def _response(channel: Channel, config_name: str | None) -> ChannelResponse:
    """Resposta do canal com só os nomes dos campos da credencial, nunca os valores."""
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
        welcome_message=channel.welcome_message,
        exit_keywords=list(channel.exit_keywords),
        webhook_path=f"/hooks/channels/{channel.id}",
        credential_fields=sorted(decrypt_json(channel.credentials_encrypted)),
        created_at=channel.created_at,
    )


def _check_credentials(kind: str, credentials: dict[str, str]) -> dict[str, str]:
    """Fica só com os campos que o provedor usa, sem vazios, e exige todos eles."""
    needed = providers.CREDENTIAL_FIELDS[kind]
    cleaned = {
        field: value.strip()
        for field, value in credentials.items()
        if field in needed and value.strip()
    }
    missing = [field for field in needed if field not in cleaned]
    if missing:
        raise HTTPException(status_code=422, detail=f"Faltam na credencial: {', '.join(missing)}")
    if any(len(value) > 2000 for value in cleaned.values()):
        raise HTTPException(status_code=422, detail="Credencial grande demais")
    return cleaned


def _seal(credentials: dict[str, str]) -> str:
    """Cifra a credencial; sem a chave de segredos configurada, 422 em vez de 500."""
    try:
        return encrypt_json(credentials)
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _config_or_422(session: SessionDep, config_id: UUID) -> AgentConfig:
    """Canal só liga agente ou time com versão publicada: o rascunho não atende cliente."""
    config = session.get(AgentConfig, config_id)
    if config is None or config.kind not in ("agent", "team"):
        raise HTTPException(status_code=422, detail="Escolha um agente ou time")
    if config.current_version_id is None:
        raise HTTPException(status_code=422, detail="Publique o agente antes de ligar um canal")
    return config


def _with_warnings(
    response: ChannelResponse, session: SessionDep, config: AgentConfig
) -> ChannelResponse:
    """Tool com confirmação humana pausa o run, e no canal não há quem aprove (LLM-12)."""
    from app.models.config import AgentConfigVersion
    from app.schemas.config import ConfigPayload

    version = session.get(AgentConfigVersion, config.current_version_id)
    if version is None:
        return response
    payload = ConfigPayload.model_validate(version.payload)
    if any(binding.require_confirmation for binding in payload.mcp_servers):
        response.warnings.append(
            "O agente tem tool com confirmação humana. No canal o run pausa e a conversa"
            " passa para um atendente; a tool só roda depois da aprovação na página Aprovações."
        )
    return response


def _channel_or_404(session: SessionDep, channel_id: UUID) -> Channel:
    channel = session.get(Channel, channel_id)
    if channel is None:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    return channel


def _actor(request: Request) -> str:
    """Quem fez a escrita; "panel" quando a requisição não traz usuário."""
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
    credentials = _check_credentials(body.kind, body.credentials)
    channel = Channel(
        kind=body.kind,
        name=body.name.strip(),
        config_id=config.id,
        enabled=body.enabled,
        credentials_encrypted=_seal(credentials),
        handoff_enabled=body.handoff_enabled,
        handoff_keywords=body.handoff_keywords,
        handoff_message=body.handoff_message,
        welcome_message=body.welcome_message.strip(),
        exit_keywords=body.exit_keywords,
        created_by=_actor(request),
    )
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return _with_warnings(_response(channel, config.name), session, config)


@router.put("/{channel_id}", response_model=ChannelResponse)
def update_channel(channel_id: UUID, body: ChannelUpdate, session: SessionDep) -> ChannelResponse:
    channel = _channel_or_404(session, channel_id)
    config = _config_or_422(session, body.config_id)
    if body.credentials:
        # troca só os campos enviados e mantém os outros da credencial atual
        merged = {**decrypt_json(channel.credentials_encrypted), **body.credentials}
        channel.credentials_encrypted = _seal(_check_credentials(channel.kind, merged))
    channel.name = body.name.strip()
    channel.config_id = config.id
    channel.enabled = body.enabled
    channel.handoff_enabled = body.handoff_enabled
    channel.handoff_keywords = body.handoff_keywords
    channel.handoff_message = body.handoff_message
    channel.welcome_message = body.welcome_message.strip()
    channel.exit_keywords = body.exit_keywords
    session.commit()
    session.refresh(channel)
    return _with_warnings(_response(channel, config.name), session, config)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: UUID, session: SessionDep) -> Response:
    session.delete(_channel_or_404(session, channel_id))
    session.commit()
    return Response(status_code=204)


@router.post("/{channel_id}/test", response_model=ChannelTest)
def test_channel(channel_id: UUID, session: SessionDep) -> ChannelTest:
    """Confere a credencial no provedor sem mandar mensagem a ninguém."""
    channel = _channel_or_404(session, channel_id)
    credentials = decrypt_json(channel.credentials_encrypted)
    try:
        with providers._http() as client:
            if channel.kind == "whatsapp":
                # leitura do número na Graph API: falha se o token não vale para ele
                graph_response = client.get(
                    f"{providers.GRAPH_URL}/{credentials['phone_number_id']}",
                    params={"fields": "display_phone_number"},
                    headers={"Authorization": f"Bearer {credentials['access_token']}"},
                )
                if graph_response.status_code != 200:
                    return ChannelTest(
                        ok=False, detail=f"Meta recusou ({graph_response.status_code})"
                    )
                number = graph_response.json().get("display_phone_number", "")
                return ChannelTest(ok=True, detail=f"Número {number}".strip())
            # o Slack responde 200 com ok=false para token inválido
            slack_response = client.post(
                f"{providers.SLACK_URL}/auth.test",
                headers={"Authorization": f"Bearer {credentials['bot_token']}"},
            )
            slack_reply = slack_response.json() if slack_response.status_code < 500 else {}
            if not slack_reply.get("ok"):
                return ChannelTest(
                    ok=False,
                    detail=f"Slack recusou: {slack_reply.get('error', slack_response.status_code)}",
                )
            return ChannelTest(ok=True, detail=f"Workspace {slack_reply.get('team', '')}".strip())
    except (httpx.HTTPError, ValueError) as exc:
        return ChannelTest(ok=False, detail=f"Sem resposta do provedor: {exc.__class__.__name__}")
