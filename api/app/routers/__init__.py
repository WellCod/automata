from fastapi import APIRouter

from app.routers.approvals import router as approvals_router
from app.routers.budget import router as budget_router
from app.routers.configs import router as configs_router
from app.routers.evals import router as evals_router
from app.routers.evals import runs_router as eval_runs_router
from app.routers.evals import schedule_router as eval_schedule_router
from app.routers.evals import settings_router as eval_settings_router
from app.routers.evals import status_router as eval_status_router
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
from app.routers.users import me_router
from app.routers.users import router as users_router

# Rotas /api/v1 montadas dentro do AgentOS (atrás do JWT). main.py e o export
# do OpenAPI usam a mesma lista para os tipos do painel não divergirem.
PROTECTED_ROUTERS: list[APIRouter] = [
    approvals_router,
    budget_router,
    configs_router,
    evals_router,
    eval_runs_router,
    eval_schedule_router,
    eval_settings_router,
    eval_status_router,
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
    users_router,
    me_router,
]
