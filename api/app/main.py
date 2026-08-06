from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.agent.protocol import AgentProtocol
from agno.agent.remote import RemoteAgent
from agno.db.postgres import PostgresDb
from agno.os import AgentOS
from fastapi import FastAPI

from app.routers.models import router as models_router
from app.settings import get_settings


def create_app(auto_provision_dbs: bool = True) -> FastAPI:
    settings = get_settings()
    db = PostgresDb(db_url=settings.database_url)

    base = FastAPI(title="automata")
    base.include_router(models_router)

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
    ).get_app()


app = create_app()
