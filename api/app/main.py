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
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.agents.factory import make_agent_factory
from app.agents.registry import PublishedAgents
from app.logging_config import configure_logging, request_id_var
from app.mcp_auth import JWTMCPAuth
from app.rate_limit import make_rate_limiter
from app.routers.auth import router as auth_router
from app.routers.configs import router as configs_router
from app.routers.health import router as health_router
from app.routers.linter import router as linter_router
from app.routers.metrics import router as metrics_router
from app.routers.models import router as models_router
from app.routers.runs import router as runs_router
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


AgentList = list[Agent | RemoteAgent | AgentProtocol | AgentFactory]


_RUNTIME_PREFIXES = ("/agents", "/teams", "/mcp", "/config")


class SyncPublishedAgentsMiddleware(BaseHTTPMiddleware):
    """Registra no AgentOS configs publicados por outros workers antes de rotas do runtime."""

    def __init__(self, app: object, published: PublishedAgents) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._published = published

    async def dispatch(self, request: Request, call_next: object) -> Response:
        if request.url.path.startswith(_RUNTIME_PREFIXES) and self._published.is_stale():
            await run_in_threadpool(self._published.sync)
        response: Response = await call_next(request)  # type: ignore[operator]
        return response


def create_app(
    auto_provision_dbs: bool = True,
    enable_auth: bool = True,
    enable_mcp_server: bool = True,
) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    db = PostgresDb(db_url=settings.database_url)

    base = FastAPI(title="automata")
    base.state.enforce_scopes = enable_auth
    base.include_router(configs_router)
    base.include_router(models_router)
    base.include_router(linter_router)
    base.include_router(metrics_router)
    base.include_router(runs_router)
    base.include_router(usage_router)

    auth_config: AuthorizationConfig | None = None
    if enable_auth:
        auth_config = AuthorizationConfig(
            verification_keys=[settings.jwt_public_key],
            algorithm="RS256",
            user_isolation=True,
        )

    # Lista compartilhada com o AgentOS, que a lê a cada request
    factories: AgentList = []
    published = PublishedAgents(factories, lambda config_id: make_agent_factory(config_id, db))
    published.sync()
    base.state.published_agents = published

    mcp_auth = JWTMCPAuth() if enable_auth and enable_mcp_server else None

    protected = AgentOS(
        id="automata",
        db=db,
        agents=factories,
        base_app=base,
        auto_provision_dbs=auto_provision_dbs,
        authorization=enable_auth,
        authorization_config=auth_config,
        mcp_server=enable_mcp_server,
        mcp_auth=mcp_auth,
    ).get_app()

    # auth_router fica fora do middleware do Agno: /login precisa ser público
    # (não tem como exigir JWT para obter JWT). O /users tem proteção própria
    # via _require_admin que verifica JWT + scope agent_os:admin.
    outer: FastAPI = FastAPI(title="automata")
    outer.state.rate_limiter = make_rate_limiter(settings.redis_url, limit=5, window=60)
    outer.add_middleware(SyncPublishedAgentsMiddleware, published=published)
    outer.add_middleware(SecurityHeadersMiddleware)
    outer.add_middleware(RequestIDMiddleware)
    outer.include_router(auth_router)
    outer.include_router(health_router)
    outer.mount("/", protected)
    return outer


app = create_app()
