from fastapi import APIRouter

from app.routers.approvals import router as approvals_router
from app.routers.configs import router as configs_router
from app.routers.integrations import router as integrations_router
from app.routers.knowledge_bases import router as knowledge_bases_router
from app.routers.knowledge_contents import router as knowledge_contents_router
from app.routers.linter import router as linter_router
from app.routers.mcp_servers import router as mcp_servers_router
from app.routers.metrics import router as metrics_router
from app.routers.models import router as models_router
from app.routers.runs import router as runs_router
from app.routers.traces import router as traces_router
from app.routers.usage import router as usage_router

# Rotas /api/v1 montadas dentro do AgentOS (atrás do JWT). main.py e o export
# do OpenAPI usam a mesma lista para os tipos do painel não divergirem.
PROTECTED_ROUTERS: list[APIRouter] = [
    approvals_router,
    configs_router,
    integrations_router,
    knowledge_bases_router,
    knowledge_contents_router,
    models_router,
    linter_router,
    mcp_servers_router,
    metrics_router,
    runs_router,
    traces_router,
    usage_router,
]
