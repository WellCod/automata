"""Seed de instância — idempotente para qualquer conjunto."""

import logging
import os

from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.repositories.config import ConfigRepository
from app.repositories.user import UserRepository
from app.schemas.config import CapabilityFlags, ConfigPayload, InstructionSections
from app.services.config import ConfigService
from app.services.user import UserService

logger = logging.getLogger(__name__)

_DEMO_AGENTS: list[dict] = [  # type: ignore[type-arg]
    {
        "name": "Suporte ao Cliente",
        "description": "Atendimento de dúvidas e resolução de problemas para clientes",
        "payload": ConfigPayload(
            model_id="claude-haiku-4-5",
            instructions=InstructionSections(
                persona="Assistente de suporte amigável e prestativo.",
                objective="Resolver dúvidas e problemas dos clientes de forma eficiente.",
                tone="Educado, empático e objetivo.",
                guardrails="Não compartilhe dados confidenciais. Não faça promessas sem respaldo.",
            ),
        ),
    },
    {
        "name": "Assistente de Código",
        "description": "Revisão, debugging e geração de código em múltiplas linguagens",
        "payload": ConfigPayload(
            model_id="claude-sonnet-4-6",
            instructions=InstructionSections(
                persona="Engenheiro de software sênior especialista em múltiplas linguagens.",
                objective="Auxiliar com revisão de código, debugging e implementação.",
                tone="Técnico, direto e preciso.",
                guardrails="Explique o raciocínio das sugestões. Nunca produza código inseguro.",
            ),
            capabilities=CapabilityFlags(extended_thinking=True),
        ),
    },
]


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
