"""Limite de runs por quem chama (LLM-05).

As rotas de run e o `/mcp` não tinham limite: um token de integração vazado usava o
agente como proxy de LLM pago pela instância. O sub do token vem do `current_actor`,
que o `RevocationMiddleware` põe antes; sem ele a request não tem token e o Agno recusa.
"""

import re

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.integrations import current_actor
from app.settings import get_settings

_RUN = re.compile(r"^/(agents|teams|workflows)/[^/]+/runs(/[^/]+/continue)?/?$")


class RunRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        path = request.url.path
        limited = request.method == "POST" and (_RUN.match(path) or path.startswith("/mcp"))
        limit = get_settings().run_rate_limit_per_minute
        actor = current_actor.get()
        limiter = getattr(request.app.state, "rate_limiter", None)
        if limited and limit > 0 and actor and limiter is not None:
            try:
                await run_in_threadpool(limiter.check, f"runs:{actor}", limit)
            except HTTPException as exc:
                return JSONResponse(
                    {"detail": "Limite de execuções por minuto atingido. Tente em instantes."},
                    status_code=exc.status_code,
                )
        response: Response = await call_next(request)  # type: ignore[operator]
        return response
