"""Webhook de aviso da suíte agendada (ADR-0018).

A URL e o segredo ficam cifrados juntos no agendamento. Cada envio passa pelo
mesmo filtro de saída dos servidores MCP, no cadastro e na hora de mandar,
porque o DNS pode mudar depois do cadastro. A entrega nunca levanta: devolve o
resultado para ficar gravado no agendamento.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.mcp.egress import EgressDenied, check_url, guarded_client
from app.secrets import decrypt_json, encrypt_json

logger = logging.getLogger(__name__)

TIMEOUT_S = 10.0
# espera antes da 2ª e da 3ª tentativa
RETRY_WAITS_S = (1.0, 5.0)
SIGNATURE_HEADER = "X-Automata-Signature"
EVENT_HEADER = "X-Automata-Event"


@dataclass(frozen=True)
class Webhook:
    url: str
    secret: str


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def seal(url: str) -> tuple[str, str, str]:
    """Valida a URL e devolve (cifrado, host, segredo novo). O segredo é mostrado uma vez."""
    check_url(url)
    secret = secrets.token_urlsafe(32)
    return encrypt_json({"url": url, "secret": secret}), host_of(url), secret


def unseal(encrypted: str) -> Webhook:
    data = decrypt_json(encrypted)
    return Webhook(url=data["url"], secret=data["secret"])


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def body_for(event: str, data: dict[str, Any], text: str) -> bytes:
    """JSON com `text` (Slack, Teams) e `content` (Discord): cola no canal sem adaptador."""
    payload = {
        "event": event,
        "at": datetime.now(UTC).isoformat(),
        **data,
        "text": text,
        "content": text,
    }
    return json.dumps(payload, ensure_ascii=False).encode()


def deliver(webhook: Webhook, event: str, body: bytes, *, attempts: int = 3) -> str:
    """Manda e devolve o resultado legível: "HTTP 200" ou o motivo da falha."""
    try:
        check_url(webhook.url)
    except EgressDenied as exc:
        return f"recusado: {exc}"
    headers = {
        "Content-Type": "application/json",
        SIGNATURE_HEADER: sign(webhook.secret, body),
        EVENT_HEADER: event,
    }
    result = "sem tentativa"
    for attempt in range(attempts):
        if attempt:
            time.sleep(RETRY_WAITS_S[min(attempt - 1, len(RETRY_WAITS_S) - 1)])
        try:
            # sem seguir redirect, com o IP conferido de novo na conexão
            with guarded_client(timeout=TIMEOUT_S) as client:
                response = client.post(webhook.url, content=body, headers=headers)
        except EgressDenied as exc:
            # o DNS mudou desde o check: o IP conferido na conexão caiu em rede interna
            return f"recusado: {exc}"
        except httpx.HTTPError as exc:
            result = f"erro: {type(exc).__name__}"
            continue
        result = f"HTTP {response.status_code}"
        if response.is_success:
            return result
        # 4xx não melhora repetindo: URL errada, webhook apagado do outro lado
        if 400 <= response.status_code < 500:
            break
    logger.warning(
        "webhook da suíte não entregue", extra={"host": host_of(webhook.url), "result": result}
    )
    return result
