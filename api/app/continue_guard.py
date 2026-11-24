"""O `continue` só aprova a tool que estava pendente, com os mesmos argumentos (LLM-03).

A rota de continue do AgentOS monta `ToolExecution.from_dict` com o que vem no form e o
Agno troca a tool gravada pela do cliente, casando só pelo `tool_call_id`. Quem iniciou o
run podia aprovar a própria pendência com outro nome ou outros argumentos: a confirmação
humana não garantia que o executado era o que foi mostrado.
"""

import json
import re
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.types import Message

from app.db import get_engine
from app.models.run import AgentRun

_CONTINUE = re.compile(r"^/(agents|teams)/[^/]+/runs/(?P<run_id>[^/]+)/continue/?$")
MAX_BODY = 1024 * 1024
_FORMS = ("application/x-www-form-urlencoded", "multipart/form-data")
MISMATCH = "A tool enviada não é a que estava pendente de aprovação neste run"


def _pending(run_id: str) -> list[dict[str, Any]] | None:
    """Tools pendentes gravadas no run; None quando o run não existe ou não tem pendência."""
    with Session(get_engine()) as session:
        rows = session.scalars(
            select(AgentRun.pending_tools).where(AgentRun.run_id == run_id).limit(1)
        ).all()
    return rows[0] if rows and rows[0] else None


def mismatch(pending: list[dict[str, Any]], sent: list[Any]) -> bool:
    """Alguma tool enviada difere da pendente de mesmo `tool_call_id`, ou não existia."""
    pending_by_call_id = {tool.get("tool_call_id"): tool for tool in pending}
    for tool in sent:
        if not isinstance(tool, dict):
            return True
        original = pending_by_call_id.get(tool.get("tool_call_id"))
        if original is None:
            return True
        if tool.get("tool_name") != original.get("tool_name"):
            return True
        if (tool.get("tool_args") or {}) != (original.get("tool_args") or {}):
            return True
    return False


class ContinueGuardMiddleware(BaseHTTPMiddleware):
    """Recusa com 409 o continue cuja tool não bate com a pendente gravada no run."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        match = _CONTINUE.match(request.url.path) if request.method == "POST" else None
        if match is not None:
            refused = await self._check(request, match.group("run_id"))
            if refused is not None:
                return refused
        response: Response = await call_next(request)  # type: ignore[operator]
        return response

    async def _check(self, request: Request, run_id: str) -> Response | None:
        """Resposta de recusa, ou None para o continue seguir até a rota do Agno.

        Só o campo `tools` do form é conferido: é por ele que o cliente troca a tool
        gravada. Form ilegível, sem `tools` ou run sem pendência gravada segue adiante.
        """
        content_type = request.headers.get("content-type", "")
        if not content_type.startswith(_FORMS):
            return None
        content_length = request.headers.get("content-length", "")
        if not content_length.isdigit() or int(content_length) > MAX_BODY:
            return JSONResponse({"detail": "Corpo do continue grande demais"}, status_code=413)
        # o corpo fica em cache e a rota do Agno lê de novo; o form é lido de uma cópia
        body = await request.body()

        async def receive() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        form_request = StarletteRequest(request.scope, receive)
        try:
            form = await form_request.form()
        except Exception:
            return None
        try:
            tools_field = form.get("tools")
        finally:
            await form.close()
        if not isinstance(tools_field, str) or not tools_field.strip():
            return None
        try:
            sent = json.loads(tools_field)
        except json.JSONDecodeError:
            return None
        if not isinstance(sent, list):
            return None
        pending = await run_in_threadpool(_pending, run_id)
        if pending is None:
            return None
        if mismatch(pending, sent):
            return JSONResponse({"detail": MISMATCH}, status_code=409)
        return None
