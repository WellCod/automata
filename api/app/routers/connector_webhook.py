"""Webhook da origem de um conector (ADR-0039): rota pública, fora do JWT.

O segredo é a única defesa: HMAC-SHA256 do corpo, no formato do GitHub
(`X-Hub-Signature-256: sha256=<hex>`) ou em `X-Automata-Signature`, comparado em tempo
constante. O conteúdo do evento não é lido: a sincronização lista a origem de novo.
"""

import hashlib
import hmac
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_engine
from app.knowledge.connector_sync import sync
from app.models.knowledge_connector import KnowledgeConnector
from app.secrets import SecretsKeyMissing, decrypt_json

logger = logging.getLogger(__name__)

MAX_BODY = 1024 * 1024
# um push com vários commits chega como vários eventos: uma sincronização basta
PER_MINUTE = 1

router = APIRouter(prefix="/api/v1/knowledge-connectors", tags=["knowledge-webhook"])


def signature_ok(secret: str, body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256=").strip())


def _not_found() -> HTTPException:
    # conector inexistente e conector sem webhook respondem igual: nada a enumerar
    return HTTPException(status_code=404, detail="Webhook não encontrado")


@router.post("/{connector_id}/webhook", status_code=202)
async def receive(
    connector_id: UUID, request: Request, background: BackgroundTasks
) -> dict[str, str]:
    length = int(request.headers.get("content-length") or 0)
    if length > MAX_BODY:
        raise HTTPException(status_code=413, detail="Corpo grande demais")
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Corpo grande demais")
    with Session(get_engine()) as session:
        connector = session.get(KnowledgeConnector, connector_id)
        if connector is None or connector.webhook_secret_encrypted is None:
            raise _not_found()
        try:
            secret = decrypt_json(connector.webhook_secret_encrypted)["secret"]
        except (SecretsKeyMissing, KeyError) as exc:
            raise _not_found() from exc
        header = request.headers.get("x-hub-signature-256") or request.headers.get(
            "x-automata-signature"
        )
        if not signature_ok(secret, body, header):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
        limiter = getattr(request.app.state, "rate_limiter", None)
        if limiter is not None:
            limiter.check(f"connector-webhook:{connector_id}", limit=PER_MINUTE)
        if connector.last_status == "running":
            return {"status": "running"}
        connector.last_status = "running"
        connector.last_message = None
        session.commit()
    logger.info(
        "sincronização pelo webhook da origem",
        extra={"connector_id": str(connector_id), "at": datetime.now(UTC).isoformat()},
    )
    background.add_task(sync, connector_id)
    return {"status": "queued"}
