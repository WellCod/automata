"""Sessão da conversa nova definida antes de o AgentOS montar o agente (ADR-0040, Fase 49).

O Agno chama a factory antes de gerar o `session_id` de uma conversa sem sessão, e o
canário sorteava a primeira mensagem à parte: a conversa trocava de versão no segundo
turno. Quando o form não traz `session_id`, este middleware gera um e põe em
`request.state.session_id`, que a rota de run do Agno usa no lugar do form.
"""

import re
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import Message

_RUN = re.compile(r"^/(agents|teams)/[^/]+/runs/?$")
# corpo maior que isso (anexo grande) segue sem sessão gerada: não vale bufferizar aqui
MAX_BODY = 10 * 1024 * 1024
_FORMS = ("application/x-www-form-urlencoded", "multipart/form-data")


class SessionIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.method == "POST" and _RUN.match(request.url.path):
            await self._ensure_session(request)
        response: Response = await call_next(request)  # type: ignore[operator]
        return response

    async def _ensure_session(self, request: Request) -> None:
        content_type = request.headers.get("content-type", "")
        length = request.headers.get("content-length", "")
        if not content_type.startswith(_FORMS) or not length.isdigit():
            return
        if int(length) > MAX_BODY:
            return
        # o corpo fica em cache e a rota do Agno lê de novo; o form é lido de uma cópia
        body = await request.body()

        async def receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        copy = StarletteRequest(request.scope, receive)
        try:
            form = await copy.form()
        except Exception:
            return
        try:
            if not str(form.get("session_id") or "").strip():
                request.state.session_id = str(uuid.uuid4())
        finally:
            await form.close()
