"""Webhook da origem de um conector (ADR-0039): rota pública, fora do JWT.

O segredo é a única defesa: HMAC-SHA256 do corpo, no formato do GitHub
(`X-Hub-Signature-256: sha256=<hex>`) ou em `X-Automata-Signature`, comparado em tempo
constante. O conteúdo do evento não é lido: a sincronização lista a origem de novo.
"""

import asyncio
import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.jobs import submit
from app.models.knowledge_connector import KnowledgeConnector
from app.proxy import get_client_ip
from app.secrets import SecretsKeyMissing, decrypt_json

logger = logging.getLogger(__name__)

MAX_BODY = 1024 * 1024
# um push com vários commits chega como vários eventos: uma sincronização basta
PER_MINUTE = 1
# por IP, antes da consulta: quem não tem o segredo não ocupa o banco à vontade
PER_IP_MINUTE = 60

router = APIRouter(prefix="/api/v1/knowledge-connectors", tags=["knowledge-webhook"])


def signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest().encode()
    # em bytes: compare_digest com str fora do ASCII levanta TypeError
    given = header.removeprefix("sha256=").strip().encode("utf-8", "replace")
    return hmac.compare_digest(expected, given)


def _not_found() -> HTTPException:
    # conector inexistente e conector sem webhook respondem igual: nada a enumerar
    return HTTPException(status_code=404, detail="Webhook não encontrado")


async def _read_body(request: Request) -> bytes:
    """Lê o corpo cortando no teto: `chunked` não traz `content-length` (Fase 43)."""
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise HTTPException(status_code=400, detail="Content-Length inválido")
        if int(declared) > MAX_BODY:
            raise HTTPException(status_code=413, detail="Corpo grande demais")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BODY:
            raise HTTPException(status_code=413, detail="Corpo grande demais")
        chunks.append(chunk)
    return b"".join(chunks)


def _claim(connector_id: UUID, body: bytes, header: str | None, limiter: Any) -> str:
    """Confere a assinatura e marca a sincronização; roda numa thread, fora do event loop."""
    with Session(get_engine()) as session:
        connector = session.get(KnowledgeConnector, connector_id)
        if connector is None or connector.webhook_secret_encrypted is None:
            raise _not_found()
        try:
            secret = decrypt_json(connector.webhook_secret_encrypted)["secret"]
        except (SecretsKeyMissing, KeyError) as exc:
            raise _not_found() from exc
        if not signature_ok(secret, body, header):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
        if limiter is not None:
            limiter.check(f"connector-webhook:{connector_id}", limit=PER_MINUTE)
        if connector.last_status == "running":
            return "running"
        connector.last_status = "running"
        connector.last_message = None
        session.commit()
    return "queued"


@router.post("/{connector_id}/webhook", status_code=202)
async def receive(
    connector_id: UUID, request: Request, background: BackgroundTasks
) -> dict[str, str]:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        # antes de tocar no banco: rota pública, sem token
        await asyncio.to_thread(
            limiter.check, f"connector-webhook-ip:{get_client_ip(request)}", PER_IP_MINUTE
        )
    body = await _read_body(request)
    header = request.headers.get("x-hub-signature-256") or request.headers.get(
        "x-automata-signature"
    )
    status = await asyncio.to_thread(_claim, connector_id, body, header, limiter)
    if status == "running":
        return {"status": "running"}
    logger.info(
        "sincronização pelo webhook da origem",
        extra={"connector_id": str(connector_id), "at": datetime.now(UTC).isoformat()},
    )
    submit(background, "sync", connector_id)
    return {"status": "queued"}
