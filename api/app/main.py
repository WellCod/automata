from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.agent.protocol import AgentProtocol
from agno.agent.remote import RemoteAgent
from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from agno.os.config import AuthorizationConfig
from fastapi import FastAPI

from app.routers.configs import router as configs_router
from app.routers.linter import router as linter_router
from app.routers.models import router as models_router
from app.routers.usage import router as usage_router
from app.settings import get_settings


def create_app(
    auto_provision_dbs: bool = True,
    enable_auth: bool = True,
) -> FastAPI:
    settings = get_settings()
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

    return AgentOS(
        id="automata",
        db=db,
        agents=factories or None,
        base_app=base,
        auto_provision_dbs=auto_provision_dbs,
        authorization=enable_auth,
        authorization_config=auth_config,
    ).get_app()


app = create_app()
