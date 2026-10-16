"""Autorização por scope nas rotas próprias (/api/v1).

O middleware JWT do AgentOS valida assinatura e popula request.state.scopes,
mas só exige scope nas rotas do mapa padrão dele. As rotas próprias declaram
o scope exigido com estas dependências.
"""

from collections.abc import Callable

from agno.os.scopes import has_required_scopes
from fastapi import HTTPException, Request


class Scope:
    CONFIGS_READ = "configs:read"
    CONFIGS_WRITE = "configs:write"
    CONFIGS_PUBLISH = "configs:publish"
    METRICS_READ = "metrics:read"
    MCP_SERVERS_READ = "mcp_servers:read"
    # Define para onde a API conecta e com qual credencial: nenhum papel além do
    # owner (agent_os:admin) recebe este scope
    MCP_SERVERS_WRITE = "mcp_servers:write"
    # Bases de conhecimento (ADR-0012): editor cria e alimenta, viewer consulta
    KNOWLEDGE_READ = "knowledge_bases:read"
    KNOWLEDGE_WRITE = "knowledge_bases:write"
    # Emitir token para terceiros: também só owner
    INTEGRATIONS_WRITE = "integrations:write"


def require_scopes(*required: str) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        # Sem auth (testes e create_app(enable_auth=False)) o app não marca a flag
        if not getattr(request.app.state, "enforce_scopes", False):
            return
        user_scopes: list[str] = getattr(request.state, "scopes", None) or []
        admin_scope: str | None = getattr(request.state, "admin_scope", None)
        if not has_required_scopes(user_scopes, list(required), admin_scope=admin_scope):
            raise HTTPException(status_code=403, detail="Permissão insuficiente")

    return dependency
