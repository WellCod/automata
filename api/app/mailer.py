"""Aviso por e-mail pelo SMTP da empresa (ADR-0037).

Configuração só pelo ambiente: SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD,
SMTP_FROM e SMTP_STARTTLS (true). Sem SMTP_HOST o tipo e-mail não é oferecido.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

TIMEOUT_S = 10.0
SENT = "SMTP enviado"


def configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def send(to: list[str], subject: str, text: str) -> str:
    """Status curto para `last_status` do destino; nunca levanta."""
    host = os.environ.get("SMTP_HOST", "")
    if not host:
        return "recusado: SMTP_HOST não configurado"
    sender = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER") or "automata@localhost"
    message = EmailMessage()
    message["From"] = sender
    message["To"] = ", ".join(to)
    message["Subject"] = subject
    message.set_content(text)
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=TIMEOUT_S) as smtp:
            if os.environ.get("SMTP_STARTTLS", "true").lower() != "false":
                smtp.starttls()
            user = os.environ.get("SMTP_USER")
            if user:
                smtp.login(user, os.environ.get("SMTP_PASSWORD", ""))
            smtp.send_message(message)
    except Exception as exc:
        # o servidor pode ecoar endereço ou credencial: só o tipo vai para o log
        logger.warning("e-mail de aviso falhou", extra={"error": type(exc).__name__})
        return f"falhou: {type(exc).__name__}"
    return SENT
