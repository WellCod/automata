import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.db.base import AsyncBaseDb, BaseDb
from agno.factory.utils import FactoryValidationError, RequestContext
from agno.tools.mcp import MCPTools
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.models_map import resolve_model
from app.agents.tracking import TrackedAgent
from app.db import get_engine
from app.mcp.client import build_mcp_tools
from app.mcp.egress import EgressDenied
from app.repositories.config import ConfigRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import ConfigPayload
from app.secrets import SecretsKeyMissing


class FactoryInput(BaseModel):
    version_id: UUID | None = None


@dataclass
class ResolvedVersion:
    name: str
    description: str
    payload: ConfigPayload
    mcp_tools: list[MCPTools] = field(default_factory=list)


def load_version(config_id: UUID, version_id: UUID | None) -> ResolvedVersion:
    """Versão vigente do config, ou a pedida pelo modo teste.

    A versão pedida precisa ser do próprio config: sem essa checagem dava para
    rodar o agente A com prompt e modelo de B, com run e custo contados em A.
    """
    with Session(get_engine()) as session:
        repo = ConfigRepository(session)
        config = repo.get_config(config_id)
        if config is None:
            raise FactoryValidationError(f"Config {config_id} não encontrada")

        vid = version_id or config.current_version_id
        if vid is None:
            raise FactoryValidationError("Nenhuma versão publicada para este agente")

        version = repo.get_version(vid)
        if version is None or version.config_id != config_id:
            raise FactoryValidationError(f"Versão {vid} não pertence a este agente")

        payload = ConfigPayload.model_validate(version.payload)
        return ResolvedVersion(
            name=config.name,
            description=config.description,
            payload=payload,
            mcp_tools=_mcp_tools_for(session, payload),
        )


def _mcp_tools_for(session: Session, payload: ConfigPayload) -> list[MCPTools]:
    """Um MCPTools por servidor vinculado. A conexão acontece no run (TrackedAgent)."""
    servers = McpServerRepository(session).get_many([b.server_id for b in payload.mcp_servers])
    by_id = {s.id: s for s in servers}
    result: list[MCPTools] = []
    for binding in payload.mcp_servers:
        server = by_id.get(binding.server_id)
        if server is None:
            raise FactoryValidationError(f"servidor MCP {binding.server_id} não existe mais")
        try:
            result.append(
                build_mcp_tools(
                    server,
                    include_tools=binding.tools,
                    requires_confirmation=binding.require_confirmation,
                )
            )
        except (EgressDenied, SecretsKeyMissing) as exc:
            raise FactoryValidationError(f"servidor MCP '{server.slug}': {exc}") from exc
    return result


def build_instructions(payload: ConfigPayload) -> str | None:
    sections = [
        payload.instructions.persona,
        payload.instructions.situation,
        payload.instructions.tone,
        payload.instructions.objective,
        payload.instructions.guardrails,
    ]
    return "\n\n".join(s for s in sections if s) or None


def make_agent_factory(config_id: UUID, db: BaseDb | AsyncBaseDb) -> AgentFactory:
    """Cria um AgentFactory para o config_id informado.

    O factory function constrói um Agent por request lendo a versão vigente
    do banco. Se factory_input.version_id for informado, usa essa versão
    específica — comportamento de modo teste.
    """

    async def build(ctx: RequestContext) -> Agent:
        version_id = ctx.input.version_id if isinstance(ctx.input, FactoryInput) else None
        # leitura síncrona do banco fora do event loop
        resolved = await asyncio.to_thread(load_version, config_id, version_id)
        payload = resolved.payload

        agent = TrackedAgent(
            id=str(config_id),
            name=resolved.name,
            description=resolved.description,
            model=resolve_model(payload.model_id, payload.capabilities),
            instructions=build_instructions(payload),
            tools=list(resolved.mcp_tools),
        )
        agent.automata_config_id = config_id
        agent.automata_model_id = payload.model_id
        return agent

    return AgentFactory(
        id=str(config_id),
        db=db,
        factory=build,
        input_schema=FactoryInput,
    )
