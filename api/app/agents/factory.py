from uuid import UUID

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.db.base import AsyncBaseDb, BaseDb
from agno.factory.utils import RequestContext
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.models_map import resolve_model
from app.repositories.config import ConfigRepository
from app.schemas.config import ConfigPayload
from app.settings import get_settings


class FactoryInput(BaseModel):
    version_id: UUID | None = None


def make_agent_factory(config_id: UUID, db: BaseDb | AsyncBaseDb) -> AgentFactory:
    """Cria um AgentFactory para o config_id informado.

    O factory function constrói um Agent por request lendo a versão vigente
    do banco. Se factory_input.version_id for informado, usa essa versão
    específica — comportamento de modo teste.
    """

    def build(ctx: RequestContext) -> Agent:
        version_id: UUID | None = None
        if isinstance(ctx.input, FactoryInput):
            version_id = ctx.input.version_id

        engine = create_engine(get_settings().database_url)
        with Session(engine) as session:
            repo = ConfigRepository(session)
            config = repo.get_config(config_id)
            if config is None:
                raise ValueError(f"Config {config_id} não encontrada")

            vid = version_id or config.current_version_id
            if vid is None:
                raise ValueError("Nenhuma versão publicada para este agente")

            version = repo.get_version(vid)
            if version is None:
                raise ValueError(f"Versão {vid} não encontrada")

            payload = ConfigPayload.model_validate(version.payload)
            model = resolve_model(payload.model_id)

            sections = [
                payload.instructions.persona,
                payload.instructions.situation,
                payload.instructions.tone,
                payload.instructions.objective,
                payload.instructions.guardrails,
            ]
            instructions = "\n\n".join(s for s in sections if s) or None

            return Agent(
                id=str(config_id),
                model=model,
                instructions=instructions,
            )

    return AgentFactory(
        id=str(config_id),
        db=db,
        factory=build,
        input_schema=FactoryInput,
    )
