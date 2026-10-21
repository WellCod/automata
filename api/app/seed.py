"""Seed de instância — idempotente para qualquer conjunto."""

import logging
import os
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.knowledge import demo_content
from app.knowledge.embedders import EMBEDDERS, is_configured
from app.knowledge.ingest import ingest
from app.models.config import AgentConfig
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.models.user import UserRole
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.user import UserRepository
from app.schemas.config import (
    CapabilityFlags,
    ConfigKind,
    ConfigPayload,
    InstructionSections,
    KnowledgeBinding,
)
from app.schemas.workflow import WorkflowSettings
from app.services.config import ConfigService
from app.services.user import UserService
from app.settings import get_settings

logger = logging.getLogger(__name__)

_DEMO_AGENTS: list[dict] = [  # type: ignore[type-arg]
    {
        "name": "Analista Financeiro",
        "description": "Análise de balanços, valuation, projeções financeiras e due diligence",
        "payload": ConfigPayload(
            model_id="claude-opus-4-7",
            instructions=InstructionSections(
                persona=(
                    "Analista financeiro sênior com 15 anos de experiência em M&A, "
                    "valuation e reestruturação corporativa."
                ),
                objective=(
                    "Produzir análises financeiras rigorosas com dados quantitativos, "
                    "tabelas comparativas e recomendações acionáveis."
                ),
                tone=(
                    "Formal, preciso e orientado a dados. "
                    "Use tabelas e métricas sempre que possível."
                ),
                guardrails=(
                    "Sempre indique premissas e limitações da análise. "
                    "Não faça previsões sem base histórica. "
                    "Jamais recomende produtos financeiros sem análise de perfil de risco."
                ),
            ),
            capabilities=CapabilityFlags(extended_thinking=True, structured_output=True),
        ),
    },
    {
        "name": "Redator de Conteúdo",
        "description": "Criação de conteúdo B2B: blogs, LinkedIn, e-mail marketing e scripts",
        "payload": ConfigPayload(
            model_id="claude-sonnet-4-6",
            instructions=InstructionSections(
                persona=(
                    "Especialista em marketing de conteúdo com foco em B2B SaaS e tecnologia."
                ),
                objective=(
                    "Criar conteúdo de alta conversão que equilibra autoridade técnica "
                    "e acessibilidade para o público-alvo."
                ),
                tone="Direto, confiante e com personalidade. Evita jargão desnecessário.",
                guardrails=(
                    "Sempre baseie afirmações em fatos verificáveis. "
                    "Não exagere resultados ou métricas não comprovadas. "
                    "Inclua CTA claro em cada peça."
                ),
            ),
        ),
    },
    {
        "name": "Atendimento ao Cliente",
        "description": "Resolução de dúvidas, reclamações e solicitações de clientes em tempo real",
        "payload": ConfigPayload(
            model_id="claude-haiku-4-5",
            instructions=InstructionSections(
                persona=(
                    "Especialista de atendimento ao cliente treinado nas políticas, "
                    "produtos e processos da empresa."
                ),
                objective=(
                    "Resolver dúvidas e problemas dos clientes de forma eficiente e empática."
                ),
                tone=(
                    "Amigável, empático e profissional. Confirma o entendimento antes de responder."
                ),
                guardrails=(
                    "Nunca compartilhe dados de outros clientes. "
                    "Não prometa prazos sem confirmar com a equipe. "
                    "Escale casos P1 ao supervisor imediatamente."
                ),
            ),
        ),
    },
    {
        "name": "Suporte Técnico",
        "description": "Diagnóstico e resolução de incidentes técnicos de software e infra",
        "payload": ConfigPayload(
            model_id="claude-haiku-4-5",
            instructions=InstructionSections(
                persona=(
                    "Engenheiro de suporte técnico especialista em diagnóstico "
                    "e resolução de incidentes de software."
                ),
                objective=(
                    "Diagnosticar e resolver problemas técnicos com rapidez e precisão, "
                    "documentando cada passo."
                ),
                tone=(
                    "Técnico e objetivo, mas acessível para usuários não técnicos. "
                    "Explica o impacto antes da solução."
                ),
                guardrails=(
                    "Sempre confirme antes de executar ações destrutivas. "
                    "Documente todos os passos. "
                    "Escale imediatamente quando o impacto for P1 ou P2."
                ),
            ),
        ),
    },
    {
        "name": "Assistente de Código",
        "description": "Revisão de código, debugging e implementação em Python, TypeScript e Go",
        "payload": ConfigPayload(
            model_id="claude-sonnet-4-6",
            instructions=InstructionSections(
                persona=(
                    "Engenheiro de software sênior especialista em Python, TypeScript "
                    "e arquitetura de sistemas distribuídos."
                ),
                objective=(
                    "Auxiliar com revisão de código, implementação de features e debugging, "
                    "sempre priorizando segurança e clareza."
                ),
                tone=(
                    "Técnico, direto e preciso. Sempre explica o raciocínio por trás das sugestões."
                ),
                guardrails=(
                    "Nunca produza código com vulnerabilidades do OWASP Top 10. "
                    "Indique limitações de cobertura de testes. "
                    "Prefira clareza a cleverness."
                ),
            ),
            capabilities=CapabilityFlags(extended_thinking=True),
        ),
    },
]

# critério de aceite da Fase 15: triagem, duas análises em paralelo, consolidação e
# revisão financeira só quando a mensagem fala em reembolso. Etapas por nome de agente.
_WORKFLOW_NAME = "Atendimento com triagem"
_WORKFLOW_DESCRIPTION = "Use para pedidos de cliente que precisam de análise técnica e financeira"
_WORKFLOW_STEPS: list[dict[str, Any]] = [
    {"type": "step", "name": "triagem", "agent": "Atendimento ao Cliente"},
    {
        "type": "parallel",
        "name": "análises",
        "branches": [
            {"type": "step", "name": "técnica", "agent": "Suporte Técnico"},
            {"type": "step", "name": "financeira", "agent": "Analista Financeiro"},
        ],
    },
    {"type": "step", "name": "consolidação", "agent": "Atendimento ao Cliente"},
    {
        "type": "condition",
        "name": "se reembolso",
        "rule": {"kind": "contains", "source": "input", "value": "reembolso"},
        "steps": [{"type": "step", "name": "revisão", "agent": "Analista Financeiro"}],
    },
]

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-7": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "claude-haiku-4-5": (0.00025, 0.00125),
}

_AGENT_PROFILE: dict[str, dict] = {  # type: ignore[type-arg]
    "Analista Financeiro": {
        "error_rate": 0.05,
        "mu_ms": 4200,
        "sigma_ms": 800,
        "in_tok": (800, 3000),
        "out_tok": (400, 1500),
        "weight": 2,
    },
    "Redator de Conteúdo": {
        "error_rate": 0.03,
        "mu_ms": 2800,
        "sigma_ms": 600,
        "in_tok": (400, 2000),
        "out_tok": (300, 1200),
        "weight": 2,
    },
    "Atendimento ao Cliente": {
        "error_rate": 0.08,
        "mu_ms": 1100,
        "sigma_ms": 350,
        "in_tok": (100, 600),
        "out_tok": (80, 300),
        "weight": 4,
    },
    "Suporte Técnico": {
        "error_rate": 0.06,
        "mu_ms": 1400,
        "sigma_ms": 450,
        "in_tok": (150, 800),
        "out_tok": (100, 400),
        "weight": 3,
    },
    "Assistente de Código": {
        "error_rate": 0.04,
        "mu_ms": 3500,
        "sigma_ms": 900,
        "in_tok": (500, 2500),
        "out_tok": (300, 1400),
        "weight": 2,
    },
}

_ERRORS = [
    "LLM timeout after 30s",
    "Context window exceeded — reduce input size",
    "Rate limit reached, retry after 60s",
    "Invalid response format from model",
    "Connection reset by peer",
    "Model overloaded, try again later",
]

_USERS = [
    "alice@empresa.com",
    "bob@empresa.com",
    "carol@empresa.com",
    "dave@empresa.com",
    "eve@empresa.com",
]


def _random_ts(days_back: int) -> datetime:
    offset = random.uniform(0, days_back * 24 * 3600)
    return datetime.now(UTC) - timedelta(seconds=offset)


def seed_minimal(session: Session) -> None:
    email = os.environ["SEED_OWNER_EMAIL"]
    password = os.environ["SEED_OWNER_PASSWORD"]

    user_repo = UserRepository(session)
    if user_repo.get_by_email(email) is not None:
        logger.info("owner já existe: %s", email)
        return

    UserService(user_repo).create_user(email=email, password=password, role=UserRole.owner)
    session.commit()
    logger.info("owner criado: %s", email)


def seed_demo(session: Session) -> None:
    seed_minimal(session)

    email = os.environ["SEED_OWNER_EMAIL"]
    config_repo = ConfigRepository(session)
    config_svc = ConfigService(config_repo)

    for agent_def in _DEMO_AGENTS:
        existing, _ = config_svc.list_configs(q=agent_def["name"])
        if any(c.name == agent_def["name"] for c in existing):
            logger.info("agente já existe: %s", agent_def["name"])
            continue

        config = config_svc.create_config(
            name=agent_def["name"],
            description=agent_def["description"],
        )
        config_svc.save_draft(config.id, agent_def["payload"], author=email)
        config_svc.publish(config.id, author=email)
        session.commit()
        logger.info("agente criado e publicado: %s", agent_def["name"])

    seed_knowledge(session)
    seed_workflow(session)
    seed_evals(session)


def _resolve_agents(node: dict[str, Any], ids: dict[str, uuid.UUID]) -> dict[str, Any]:
    if node["type"] == "step":
        return {
            "type": "step",
            "name": node["name"],
            "agent_id": ids[node["agent"]],
            "on_error": "stop",
        }
    out = {k: v for k, v in node.items() if k not in ("steps", "branches")}
    for key in ("steps", "branches"):
        if key in node:
            out[key] = [_resolve_agents(child, ids) for child in node[key]]
    return out


def seed_workflow(session: Session) -> None:
    """Workflow de exemplo sobre os agentes da demo (ADR-0014)."""
    email = os.environ["SEED_OWNER_EMAIL"]
    config_svc = ConfigService(ConfigRepository(session))
    existing, _ = config_svc.list_configs(q=_WORKFLOW_NAME)
    if any(c.name == _WORKFLOW_NAME for c in existing):
        logger.info("workflow já existe: %s", _WORKFLOW_NAME)
        return
    agents, _ = config_svc.list_configs(kind=ConfigKind.agent, page_size=100)
    ids = {a.name: a.id for a in agents if a.current_version_id is not None}
    steps = [_resolve_agents(node, ids) for node in _WORKFLOW_STEPS]
    config = config_svc.create_config(
        name=_WORKFLOW_NAME, description=_WORKFLOW_DESCRIPTION, kind=ConfigKind.workflow
    )
    payload = ConfigPayload(workflow=WorkflowSettings.model_validate({"steps": steps}))
    config_svc.save_draft(config.id, payload, author=email)
    config_svc.publish(config.id, author=email)
    session.commit()
    logger.info("workflow criado e publicado: %s", _WORKFLOW_NAME)


_KNOWLEDGE_AGENT = "Atendimento ao Cliente"


# suíte do agente de atendimento (ADR-0015). Na demo o juiz não roda e a busca na base
# não acontece (respostas gravadas): o resultado mostra aprovado, falha e não avaliado
_EVAL_AGENT = "Atendimento ao Cliente"
_EVAL_CASES: list[dict[str, Any]] = [
    {
        "name": "responde a saudação",
        "input": "Oi, tudo bem? Preciso de ajuda com um pedido.",
        "checks": [{"type": "text", "kind": "not_empty"}],
    },
    {
        "name": "não promete prazo sem confirmar",
        "input": "Vocês garantem que meu pedido chega amanhã?",
        "checks": [{"type": "text", "kind": "not_contains", "value": "garantimos"}],
    },
    {
        "name": "consulta a política de troca",
        "input": "Comprei há 10 dias e quero trocar o tamanho. Ainda dá?",
        "checks": [
            {"type": "tools", "tools": ["buscar_politicas_atendimento"]},
            {"type": "text", "kind": "contains", "value": "troca"},
        ],
    },
    {
        "name": "tom cordial com cliente irritado",
        "input": "Já é a terceira vez que meu pedido atrasa, estou cansado disso.",
        "checks": [
            {
                "type": "judge",
                "criteria": "Reconhece o problema com empatia, pede desculpas e oferece um "
                "próximo passo concreto, sem culpar o cliente",
            }
        ],
    },
]


def seed_evals(session: Session) -> None:
    """Casos de teste de exemplo no agente de atendimento."""
    from app.models.eval import EvalCase
    from app.repositories.eval import EvalCaseRepository
    from app.schemas.eval import EvalCaseInput

    agents, _ = ConfigService(ConfigRepository(session)).list_configs(q=_EVAL_AGENT)
    agent = next((a for a in agents if a.name == _EVAL_AGENT), None)
    if agent is None:
        return
    repo = EvalCaseRepository(session)
    if repo.count(agent.id) > 0:
        logger.info("suíte de exemplo já existe")
        return
    email = os.environ["SEED_OWNER_EMAIL"]
    for position, raw in enumerate(_EVAL_CASES):
        case = EvalCaseInput.model_validate(raw)
        repo.add(
            EvalCase(
                agent_config_id=agent.id,
                name=case.name,
                input=case.input,
                checks=[c.model_dump() for c in case.checks],
                position=position,
                updated_by=email,
            )
        )
    session.commit()
    logger.info("suíte de exemplo criada em %s", _EVAL_AGENT)


def seed_knowledge(session: Session) -> None:
    """Base de políticas de atendimento ligada ao agente de atendimento (ADR-0012).

    Só roda com embedder disponível: na demo, o local do DEMO_REPLAY; numa instância
    real, a chave da Voyage ou da OpenAI.
    """
    spec = EMBEDDERS[get_settings().knowledge_default_embedder]
    if not is_configured(spec):
        logger.info("base de exemplo pulada: embedder %s sem chave", spec.name)
        return
    repo = KnowledgeBaseRepository(session)
    if repo.find_conflict(demo_content.BASE_NAME, demo_content.BASE_SLUG) is not None:
        logger.info("base de exemplo já existe")
        return
    email = os.environ["SEED_OWNER_EMAIL"]
    base_id = uuid.uuid4()
    base = repo.add(
        KnowledgeBase(
            id=base_id,
            name=demo_content.BASE_NAME,
            slug=demo_content.BASE_SLUG,
            description=demo_content.BASE_DESCRIPTION,
            embedder=spec.name,
            embedder_model=spec.model,
            dimensions=spec.dimensions,
            chunk_size=2000,
            vector_table=f"kb_{base_id.hex}",
            updated_by=email,
        )
    )
    contents = [
        KnowledgeContent(
            base_id=base.id,
            name=name,
            source_type="text",
            source=name,
            extension="txt",
            size_bytes=len(text.encode()),
            status="processing",
            created_by=email,
        )
        for name, text in demo_content.DOCUMENTS.items()
    ]
    session.add_all(contents)
    session.commit()
    for content in contents:
        ingest(content.id, demo_content.DOCUMENTS[content.name].encode())

    agents, _ = ConfigService(ConfigRepository(session)).list_configs(q=_KNOWLEDGE_AGENT)
    agent = next((a for a in agents if a.name == _KNOWLEDGE_AGENT), None)
    if agent is None or agent.current_version_id is None:
        return
    config_repo = ConfigRepository(session)
    current = config_repo.get_version(agent.current_version_id)
    assert current is not None
    payload = ConfigPayload.model_validate(current.payload)
    payload.knowledge = [KnowledgeBinding(base_id=base.id, max_results=3)]
    svc = ConfigService(config_repo, bases=repo)
    svc.save_draft(agent.id, payload, author=email)
    svc.publish(agent.id, author=email)
    session.commit()
    logger.info("base de exemplo criada e ligada a %s", _KNOWLEDGE_AGENT)


def seed_analytics(session: Session, n_runs: int = 500) -> None:
    """Cria histórico realista de execuções para demonstrar o painel Analytics.

    Distribui os runs pelos agentes com pesos realistas e gera usage events
    correspondentes com tokens e custos proporcionais ao modelo de cada agente.
    Execute após seed_demo — depende de agentes com versão publicada no banco.
    """
    configs = (
        session.execute(select(AgentConfig).options(joinedload(AgentConfig.current_version)))
        .scalars()
        .all()
    )

    agent_info: list[dict] = []  # type: ignore[type-arg]
    for config in configs:
        if config.current_version_id is None or config.current_version is None:
            continue
        # workflow não tem modelo: o consumo dele é o das etapas (ADR-0014)
        if config.kind == ConfigKind.workflow:
            continue
        model_id = config.current_version.payload.get("model_id", "claude-haiku-4-5")
        agent_info.append({"config_id": config.id, "name": config.name, "model_id": model_id})

    if not agent_info:
        logger.warning("nenhum agente com versão publicada — execute seed_demo primeiro")
        return

    weights = [_AGENT_PROFILE.get(a["name"], {}).get("weight", 2) for a in agent_info]
    agent_choices = random.choices(agent_info, weights=weights, k=n_runs)

    runs: list[AgentRun] = []
    events: list[UsageEvent] = []

    for agent in agent_choices:
        ts = _random_ts(days_back=90)
        period = ts.strftime("%Y%m")
        name = agent["name"]
        model_id = agent["model_id"]
        price_in, price_out = _MODEL_PRICING.get(model_id, (0.001, 0.005))
        profile = _AGENT_PROFILE.get(
            name,
            {
                "error_rate": 0.05,
                "mu_ms": 2000,
                "sigma_ms": 600,
                "in_tok": (300, 1500),
                "out_tok": (200, 800),
            },
        )

        status = "error" if random.random() < profile["error_rate"] else "success"
        duration_ms = max(300, int(random.gauss(profile["mu_ms"], profile["sigma_ms"])))

        run = AgentRun(
            id=uuid.uuid4(),
            agent_config_id=agent["config_id"],
            user_id=random.choice(_USERS),
            run_id=str(uuid.uuid4()),
            status=status,
            duration_ms=duration_ms if status == "success" else None,
            error=random.choice(_ERRORS) if status == "error" else None,
            created_at=ts,
        )
        runs.append(run)

        if status == "success":
            in_min, in_max = profile["in_tok"]
            out_min, out_max = profile["out_tok"]
            in_tok = random.randint(in_min, in_max)
            out_tok = random.randint(out_min, out_max)
            cost = round((in_tok / 1000) * price_in + (out_tok / 1000) * price_out, 8)
            events.append(
                UsageEvent(
                    id=uuid.uuid4(),
                    agent_config_id=agent["config_id"],
                    user_id=run.user_id,
                    run_id=run.run_id,
                    model_id=model_id,
                    period=period,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    total_tokens=in_tok + out_tok,
                    cost=cost,
                    created_at=ts,
                )
            )

    session.add_all(runs)
    session.add_all(events)
    session.commit()
    logger.info("inseridos %d runs e %d usage events", len(runs), len(events))


def seed_full(session: Session) -> None:
    """Seed completo para portfólio: owner, 5 agentes, base, workflow, suíte e 500 runs."""
    seed_demo(session)
    seed_analytics(session)
