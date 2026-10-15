from fastapi import APIRouter

from app.routers.approvals import router as approvals_router
from app.routers.configs import router as configs_router
from app.routers.linter import router as linter_router
from app.routers.mcp_servers import router as mcp_servers_router
from app.routers.metrics import router as metrics_router
from app.routers.models import router as models_router
from app.routers.runs import router as runs_router
from app.routers.usage import router as usage_router

# Rotas /api/v1 montadas dentro do AgentOS (atrás do JWT). main.py e o export
# do OpenAPI usam a mesma lista para os tipos do painel não divergirem.
PROTECTED_ROUTERS: list[APIRouter] = [
    approvals_router,
    configs_router,
    models_router,
    linter_router,
    mcp_servers_router,
    metrics_router,
    runs_router,
    usage_router,
]
