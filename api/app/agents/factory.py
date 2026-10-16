import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from agno.agent import Agent
from agno.agent.factory import AgentFactory
from agno.db.base import AsyncBaseDb, BaseDb
from agno.factory.utils import FactoryValidationError, RequestContext
from agno.team import Team, TeamMode
from agno.team.factory import TeamFactory
from agno.tools.function import Function
from agno.tools.mcp import MCPTools
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.models_map import resolve_model
from app.agents.tracking import TrackedAgent, TrackedTeam
from app.db import get_engine
from app.knowledge.tools import knowledge_instructions, knowledge_tool
from app.mcp.client import build_mcp_tools
from app.mcp.egress import EgressDenied
from app.models.knowledge_base import KnowledgeBase
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
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
    bases: list[KnowledgeBase] = field(default_factory=list)
    knowledge_tools: list[Function] = field(default_factory=list)


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
        bases = _bases_for(session, payload)
        return ResolvedVersion(
            name=config.name,
            description=config.description,
            payload=payload,
            mcp_tools=_mcp_tools_for(session, payload),
            bases=[b for b, _ in bases],
            knowledge_tools=[knowledge_tool(b, n, config_id) for b, n in bases],
        )


def _bases_for(session: Session, payload: ConfigPayload) -> list[tuple[KnowledgeBase, int]]:
    """Bases ligadas, soltas da sessão: a busca roda em outra thread, durante o run."""
    found = {
        b.id: b
        for b in KnowledgeBaseRepository(session).get_many([k.base_id for k in payload.knowledge])
    }
    result: list[tuple[KnowledgeBase, int]] = []
    for binding in payload.knowledge:
        base = found.get(binding.base_id)
        if base is None:
            raise FactoryValidationError(f"base de conhecimento {binding.base_id} não existe mais")
        session.expunge(base)
        result.append((base, binding.max_results))
    return result


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


def build_instructions(
    payload: ConfigPayload, bases: list[KnowledgeBase] | None = None
) -> str | None:
    sections = [
        payload.instructions.persona,
        payload.instructions.situation,
        payload.instructions.tone,
        payload.instructions.objective,
        payload.instructions.guardrails,
        knowledge_instructions(bases or []),
    ]
    return "\n\n".join(s for s in sections if s) or None


def _agent_from(config_id: UUID, resolved: ResolvedVersion, *, tracked: bool) -> Agent:
    payload = resolved.payload
    cls = TrackedAgent if tracked else Agent
    agent = cls(
        id=str(config_id),
        name=resolved.name,
        # em time, a descrição é o que o líder usa para decidir a quem delegar
        description=resolved.description,
        role=resolved.description,
        model=resolve_model(payload.model_id, payload.capabilities),
        instructions=build_instructions(payload, resolved.bases),
        tools=[*resolved.mcp_tools, *resolved.knowledge_tools],
    )
    if isinstance(agent, TrackedAgent):
        agent.automata_config_id = config_id
        agent.automata_model_id = payload.model_id
    return agent


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
        return _agent_from(config_id, resolved, tracked=True)

    return AgentFactory(
        id=str(config_id),
        db=db,
        factory=build,
        input_schema=FactoryInput,
    )


@dataclass
class ResolvedTeam:
    leader: ResolvedVersion
    members: list[tuple[UUID, ResolvedVersion]]


def load_team(config_id: UUID, version_id: UUID | None) -> ResolvedTeam:
    leader = load_version(config_id, version_id)
    team = leader.payload.team
    if team is None:
        raise FactoryValidationError(f"Config {config_id} não é um time")
    members = [(m.agent_id, load_version(m.agent_id, m.version_id)) for m in team.members]
    return ResolvedTeam(leader=leader, members=members)


def make_team_factory(config_id: UUID, db: BaseDb | AsyncBaseDb) -> TeamFactory:
    """Time por request: líder e membros montados das versões publicadas (ADR-0011).

    Só o time é registrado em agent_run; os membros são Agents comuns.
    """

    async def build(ctx: RequestContext) -> Team:
        version_id = ctx.input.version_id if isinstance(ctx.input, FactoryInput) else None
        resolved = await asyncio.to_thread(load_team, config_id, version_id)
        leader = resolved.leader
        settings = leader.payload.team
        assert settings is not None
        team = TrackedTeam(
            id=str(config_id),
            name=leader.name,
            description=leader.description,
            model=resolve_model(leader.payload.model_id, leader.payload.capabilities),
            instructions=build_instructions(leader.payload, leader.bases),
            tools=[*leader.mcp_tools, *leader.knowledge_tools],
            members=[_agent_from(mid, m, tracked=False) for mid, m in resolved.members],
            mode=TeamMode(settings.mode),
            max_iterations=settings.max_iterations,
            share_member_interactions=settings.share_member_interactions,
        )
        team.automata_config_id = config_id
        team.automata_model_id = leader.payload.model_id
        return team

    return TeamFactory(
        id=str(config_id),
        db=db,
        factory=build,
        input_schema=FactoryInput,
    )
