import logging
import uuid

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.agent.protocol import AgentProtocol
from agno.agent.remote import RemoteAgent
from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from agno.os.config import AuthorizationConfig
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.logging_config import configure_logging, request_id_var
from app.rate_limit import make_rate_limiter
from app.routers.auth import router as auth_router
from app.routers.configs import router as configs_router
from app.routers.health import router as health_router
from app.routers.linter import router as linter_router
from app.routers.models import router as models_router
from app.routers.usage import router as usage_router
from app.settings import get_settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        response: Response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response: Response = await call_next(request)  # type: ignore[operator]
            response.headers["X-Request-ID"] = request_id
        finally:
            request_id_var.reset(token)
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
            },
        )
        return response


def create_app(
    auto_provision_dbs: bool = True,
    enable_auth: bool = True,
    enable_mcp_server: bool = False,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    db = PostgresDb(db_url=settings.database_url)

    base = FastAPI(title="automata")
    base.include_router(configs_router)
    base.include_router(models_router)
    base.include_router(linter_router)
    base.include_router(usage_router)

    auth_config: AuthorizationConfig | None = None
    if enable_auth:
        auth_config = AuthorizationConfig(
            verification_keys=[settings.jwt_public_key],
            algorithm="RS256",
            user_isolation=True,
        )

    # Factories são carregadas dinamicamente aqui a partir dos configs ativos.
    # Exemplo de registro manual para desenvolvimento/testes:
    #
    #   from uuid import UUID
    #   from app.agents.factory import make_agent_factory
    #   factories = [make_agent_factory(UUID("<config-id>"), db)]
    #
    # O carregamento automático a partir do banco virá em PR futuro
    # junto com a camada de API REST de gerenciamento de configs.
    factories: list[Agent | RemoteAgent | AgentProtocol | AgentFactory] = []

    protected = AgentOS(
        id="automata",
        db=db,
        agents=factories or None,
        base_app=base,
        auto_provision_dbs=auto_provision_dbs,
        authorization=enable_auth,
        authorization_config=auth_config,
        mcp_server=enable_mcp_server,
    ).get_app()

    # auth_router fica fora do middleware do Agno: /login precisa ser público
    # (não tem como exigir JWT para obter JWT). O /users tem proteção própria
    # via _require_admin que verifica JWT + scope agent_os:admin.
    outer: FastAPI = FastAPI(title="automata")
    outer.state.rate_limiter = make_rate_limiter(settings.redis_url, limit=5, window=60)
    outer.add_middleware(SecurityHeadersMiddleware)
    outer.add_middleware(RequestIDMiddleware)
    outer.include_router(auth_router)
    outer.include_router(health_router)
    outer.mount("/", protected)
    return outer


app = create_app()
