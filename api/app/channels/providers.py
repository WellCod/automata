"""WhatsApp (Cloud API) e Slack (Events API): assinatura, leitura e envio (ADR-0044).

Cada provedor sabe conferir a assinatura do webhook, tirar do corpo as mensagens de
texto e mandar a resposta. A saída passa pelo `guarded_client`.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.mcp.egress import guarded_client

GRAPH_URL = "https://graph.facebook.com/v21.0"
SLACK_URL = "https://slack.com/api"
TIMEOUT_S = 15.0
# 5 minutos de tolerância no relógio do Slack, como a documentação dele pede
SLACK_MAX_AGE_S = 300
# teto de texto por mensagem de cada provedor; a resposta maior é cortada
WHATSAPP_MAX_TEXT = 4096
SLACK_MAX_TEXT = 3900

CREDENTIAL_FIELDS: dict[str, tuple[str, ...]] = {
    "whatsapp": ("access_token", "phone_number_id", "app_secret", "verify_token"),
    "slack": ("bot_token", "signing_secret"),
}


class SendError(RuntimeError):
    """O provedor recusou ou não respondeu; a mensagem fica `failed` com o motivo."""


@dataclass(frozen=True)
class Inbound:
    """Mensagem recebida, já reduzida ao que o canal usa."""

    external_id: str
    conversation_key: str
    sender: str
    text: str | None
    # para responder na mesma thread do Slack
    reply_to: dict[str, str]


def _http() -> httpx.Client:
    return guarded_client(timeout=TIMEOUT_S)


def _hmac_ok(secret: str, message: bytes, expected: str) -> bool:
    """HMAC-SHA256 em hex confere com o recebido, em tempo constante."""
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    # em bytes: str fora do ASCII levanta TypeError no compare_digest e virava 500 (SEC-09)
    return hmac.compare_digest(digest.encode(), expected.encode("utf-8", "replace"))


# --- WhatsApp -----------------------------------------------------------------


def whatsapp_signature_ok(creds: dict[str, str], body: bytes, header: str | None) -> bool:
    """Confere o `X-Hub-Signature-256` da Meta sobre o corpo cru com o app secret."""
    if not header or not header.startswith("sha256="):
        return False
    return _hmac_ok(creds["app_secret"], body, header.removeprefix("sha256="))


def whatsapp_messages(payload: dict[str, Any]) -> list[Inbound]:
    """Mensagens de quem fala com o número; status de entrega e leitura ficam de fora."""
    inbound_messages: list[Inbound] = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for message in value.get("messages") or []:
                sender = str(message.get("from") or "")
                message_id = str(message.get("id") or "")
                if not sender or not message_id:
                    continue
                # mídia, localização e afins entram com texto None
                body = (
                    (message.get("text") or {}).get("body")
                    if message.get("type") == "text"
                    else None
                )
                inbound_messages.append(
                    Inbound(
                        external_id=message_id,
                        conversation_key=sender,
                        sender=sender,
                        text=str(body) if body else None,
                        reply_to={"to": sender},
                    )
                )
    return inbound_messages


def whatsapp_send(creds: dict[str, str], reply_to: dict[str, str], text: str) -> str | None:
    """Envia texto pela Cloud API; devolve o id da mensagem no WhatsApp."""
    payload = {
        "messaging_product": "whatsapp",
        "to": reply_to["to"],
        "type": "text",
        "text": {"body": text[:WHATSAPP_MAX_TEXT]},
    }
    try:
        with _http() as client:
            response = client.post(
                f"{GRAPH_URL}/{creds['phone_number_id']}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {creds['access_token']}"},
            )
    except (httpx.HTTPError, ValueError) as exc:
        raise SendError(f"WhatsApp fora do ar: {exc.__class__.__name__}") from exc
    if response.status_code >= 400:
        detail = ""
        try:
            detail = str(response.json().get("error", {}).get("message", ""))[:200]
        except ValueError:
            detail = ""
        # 131047 é a janela de 24 horas fechada: só modelo de mensagem passa
        raise SendError(f"WhatsApp recusou ({response.status_code}): {detail}".strip())
    messages = response.json().get("messages") or [{}]
    return str(messages[0].get("id")) if messages[0].get("id") else None


# --- Slack --------------------------------------------------------------------


def slack_signature_ok(
    creds: dict[str, str],
    body: bytes,
    timestamp: str | None,
    signature: str | None,
    now: float | None = None,
) -> bool:
    """Confere a assinatura v0 do Slack e recusa pedido velho, contra replay."""
    if not timestamp or not signature or not signature.startswith("v0="):
        return False
    try:
        age = abs((now or time.time()) - int(timestamp))
    except ValueError:
        return False
    if age > SLACK_MAX_AGE_S:
        return False
    signed_base = b"v0:" + timestamp.encode() + b":" + body
    return _hmac_ok(creds["signing_secret"], signed_base, signature.removeprefix("v0="))


def slack_messages(payload: dict[str, Any]) -> list[Inbound]:
    """Mensagem direta ou menção ao app; mensagem de bot (inclusive a nossa) fica de fora."""
    if payload.get("type") != "event_callback":
        return []
    event = payload.get("event") or {}
    if event.get("type") not in ("message", "app_mention"):
        return []
    if event.get("bot_id") or event.get("subtype"):
        return []
    user, channel, text = event.get("user"), event.get("channel"), event.get("text")
    if not user or not channel:
        return []
    is_dm = event.get("channel_type") == "im"
    thread = str(event.get("thread_ts") or event.get("ts") or "")
    # mensagem direta é uma conversa só; em canal, cada thread é uma conversa
    conversation_key = str(channel) if is_dm else f"{channel}:{thread}"
    reply_target: dict[str, str] = {"channel": str(channel)}
    if not is_dm and thread:
        reply_target["thread_ts"] = thread
    return [
        Inbound(
            # o Slack reenvia com o mesmo event_id quando não recebe 200 em 3 segundos
            external_id=str(payload.get("event_id") or event.get("client_msg_id") or thread),
            conversation_key=conversation_key,
            sender=str(user),
            text=str(text) if text else None,
            reply_to=reply_target,
        )
    ]


def slack_send(creds: dict[str, str], reply_to: dict[str, str], text: str) -> str | None:
    """Envia texto pelo chat.postMessage; devolve o `ts` da mensagem no Slack."""
    try:
        with _http() as client:
            response = client.post(
                f"{SLACK_URL}/chat.postMessage",
                json={**reply_to, "text": text[:SLACK_MAX_TEXT]},
                headers={"Authorization": f"Bearer {creds['bot_token']}"},
            )
    except (httpx.HTTPError, ValueError) as exc:
        raise SendError(f"Slack fora do ar: {exc.__class__.__name__}") from exc
    # o Slack responde 200 com `ok: false` quando recusa: o corpo é que decide
    response_body = response.json() if response.status_code < 500 else {}
    if response.status_code >= 400 or not response_body.get("ok"):
        raise SendError(f"Slack recusou: {response_body.get('error') or response.status_code}")
    return str(response_body.get("ts")) if response_body.get("ts") else None


def send(kind: str, creds: dict[str, str], reply_to: dict[str, str], text: str) -> str | None:
    """Envia pelo provedor do canal; devolve o id da mensagem no provedor."""
    if kind == "whatsapp":
        return whatsapp_send(creds, reply_to, text)
    return slack_send(creds, reply_to, text)


def user_id(kind: str, sender: str) -> str:
    return f"{kind}:{sender}"
