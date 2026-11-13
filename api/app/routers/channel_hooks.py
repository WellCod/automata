"""Webhook público de cada canal (ADR-0044), no app externo, fora do JWT.

Sem a assinatura do provedor, nada além do canal é lido do banco. A resposta sai na
hora e a mensagem é processada em segundo plano: o provedor reenvia o que demora.
"""

import hmac
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.channels import providers, service
from app.db import get_engine
from app.models.channel import Channel
from app.proxy import get_client_ip
from app.secrets import decrypt_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hooks/channels", tags=["channel-hooks"])

MAX_BODY = 256 * 1024
# por IP, antes de tocar no banco: assinatura errada também custa uma consulta
PER_IP_LIMIT = 300


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Canal não encontrado")


def _channel(channel_id: UUID) -> tuple[str, dict[str, str]] | None:
    with Session(get_engine()) as session:
        channel = session.get(Channel, channel_id)
        if channel is None or not channel.enabled:
            return None
        return channel.kind, decrypt_json(channel.credentials_encrypted)


async def _body(request: Request) -> bytes:
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY:
            raise HTTPException(status_code=413, detail="Corpo grande demais")
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/{channel_id}", response_class=PlainTextResponse)
async def verify(channel_id: UUID, request: Request) -> Response:
    """Verificação do webhook do WhatsApp: devolve o `hub.challenge` com o token certo."""
    request.app.state.rate_limiter.check(
        f"channel-hook:{get_client_ip(request)}", limit=PER_IP_LIMIT
    )
    found = await run_in_threadpool(_channel, channel_id)
    if found is None or found[0] != "whatsapp":
        raise _not_found()
    params = request.query_params
    token = params.get("hub.verify_token", "")
    if params.get("hub.mode") != "subscribe" or not hmac.compare_digest(
        token, found[1]["verify_token"]
    ):
        raise HTTPException(status_code=403, detail="Token de verificação não confere")
    return PlainTextResponse(params.get("hub.challenge", ""))


@router.post("/{channel_id}")
async def receive(channel_id: UUID, request: Request, background: BackgroundTasks) -> Response:
    limiter = request.app.state.rate_limiter
    limiter.check(f"channel-hook:{get_client_ip(request)}", limit=PER_IP_LIMIT)
    body = await _body(request)
    found = await run_in_threadpool(_channel, channel_id)
    if found is None:
        raise _not_found()
    kind, creds = found
    if kind == "whatsapp":
        ok = providers.whatsapp_signature_ok(
            creds, body, request.headers.get("x-hub-signature-256")
        )
    else:
        ok = providers.slack_signature_ok(
            creds,
            body,
            request.headers.get("x-slack-request-timestamp"),
            request.headers.get("x-slack-signature"),
        )
    if not ok:
        logger.warning("canal: assinatura recusada", extra={"channel_id": str(channel_id)})
        raise HTTPException(status_code=401, detail="Assinatura inválida")
    try:
        payload: Any = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Corpo não é JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Corpo não é JSON")
    if kind == "slack" and payload.get("type") == "url_verification":
        return JSONResponse({"challenge": payload.get("challenge", "")})
    messages = (
        providers.whatsapp_messages(payload)
        if kind == "whatsapp"
        else providers.slack_messages(payload)
    )
    if messages:
        background.add_task(service.handle, channel_id, messages, limiter)
    return JSONResponse({"ok": True})
