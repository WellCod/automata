"""Seed de instância — idempotente para qualquer conjunto."""

import logging
import os
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.config import AgentConfig
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.models.user import UserRole
from app.repositories.config import ConfigRepository
from app.repositories.user import UserRepository
from app.schemas.config import CapabilityFlags, ConfigPayload, InstructionSections
from app.services.config import ConfigService
from app.services.user import UserService

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
    """Seed completo para portfólio: owner + 5 agentes publicados + 500 runs históricos."""
    seed_demo(session)
    seed_analytics(session)
