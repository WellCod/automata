import logging
import uuid

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.agent.protocol import AgentProtocol
from agno.agent.remote import RemoteAgent
from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from agno.os.config import AuthorizationConfig
from agno.team import RemoteTeam, Team
from agno.team.factory import TeamFactory
from fastapi import FastAPI, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from app.agents.factory import make_agent_factory, make_team_factory
from app.agents.registry import PublishedAgents
from app.integrations import RevocationMiddleware, RevokedTokens
from app.logging_config import configure_logging, request_id_var
from app.mcp_auth import JWTMCPAuth
from app.rate_limit import make_rate_limiter
from app.routers import PROTECTED_ROUTERS
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router
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
    for router in PROTECTED_ROUTERS:
        base.include_router(router)
    base.state.enforce_scopes = enable_auth

    auth_config: AuthorizationConfig | None = None
    if enable_auth:
        auth_config = AuthorizationConfig(
            verification_keys=[settings.jwt_public_key],
            algorithm="RS256",
            user_isolation=True,
        )

    # Lista compartilhada com o AgentOS, que a lê a cada request
    factories: AgentList = []
    teams: list[Team | RemoteTeam | TeamFactory] = []
    published = PublishedAgents(
        factories,
        lambda config_id: make_agent_factory(config_id, db),
        teams=teams,
        make_team_factory=lambda config_id: make_team_factory(config_id, db),
    )
    published.sync()
    base.state.published_agents = published
    base.state.agno_db = db if settings.tracing_enabled else None
    revoked = RevokedTokens()
    base.state.revoked_tokens = revoked

    mcp_auth = JWTMCPAuth() if enable_auth and enable_mcp_server else None

    protected = AgentOS(
        id="automata",
        db=db,
        agents=factories,
        teams=teams,
        base_app=base,
        auto_provision_dbs=auto_provision_dbs,
        authorization=enable_auth,
        authorization_config=auth_config,
        mcp_server=enable_mcp_server,
        mcp_auth=mcp_auth,
        tracing=settings.tracing_enabled,
    ).get_app()

    # auth_router fica fora do middleware do Agno: /login precisa ser público
    # (não tem como exigir JWT para obter JWT). O /users tem proteção própria
    # via _require_admin que verifica JWT + scope agent_os:admin.
    outer: FastAPI = FastAPI(title="automata")
    outer.state.rate_limiter = make_rate_limiter(settings.redis_url, limit=5, window=60)
    outer.add_middleware(SyncPublishedAgentsMiddleware, published=published)
    if enable_auth:
        outer.add_middleware(RevocationMiddleware, revoked=revoked)
    outer.add_middleware(SecurityHeadersMiddleware)
    outer.add_middleware(RequestIDMiddleware)
    outer.include_router(auth_router)
    outer.include_router(health_router)
    outer.mount("/", protected)
    return outer


app = create_app()
