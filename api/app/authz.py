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
    # credencial de conector define com que conta a API sai (ADR-0024): só owner
    KNOWLEDGE_CONNECTORS_WRITE = "knowledge_connectors:write"
    # memórias de usuários finais (ADR-0025): dado pessoal, só owner
    MEMORIES_ADMIN = "memories:admin"
    # Suíte de testes por agente e time (ADR-0015): editor escreve e roda, viewer vê
    EVALS_READ = "evals:read"
    EVALS_WRITE = "evals:write"
    EVALS_RUN = "evals:run"
    # Gestão de usuários: só owner
    USERS_ADMIN = "users:admin"
    # Emitir token para terceiros: também só owner
    INTEGRATIONS_WRITE = "integrations:write"
    # estado da rotação das chaves da instância (ADR-0026): só owner
    KEYS_ADMIN = "keys:admin"


def require_resource_scope(resource: str, action: str) -> Callable[[Request], None]:
    """Escopo global (`evals:run`) ou do recurso do path (`evals:<config_id>:run`).

    O recurso vem do `config_id` da rota. Tokens de integração recebem só o
    escopo por recurso; os papéis do painel, o global.
    """

    def dependency(request: Request) -> None:
        if not getattr(request.app.state, "enforce_scopes", False):
            return
        user_scopes: list[str] = getattr(request.state, "scopes", None) or []
        admin_scope: str | None = getattr(request.state, "admin_scope", None)
        resource_id = str(request.path_params.get("config_id", "")) or None
        allowed = has_required_scopes(
            user_scopes,
            [f"{resource}:{action}"],
            resource_type=resource,
            resource_id=resource_id,
            admin_scope=admin_scope,
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="Permissão insuficiente")

    return dependency


def sees_everyone(request: Request) -> bool:
    """Owner (admin) ou app sem autenticação: enxerga dados de conversa de todos os usuários."""
    if not getattr(request.app.state, "enforce_scopes", False):
        return True
    admin = getattr(request.state, "admin_scope", None) or "agent_os:admin"
    return admin in (getattr(request.state, "scopes", None) or [])


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
