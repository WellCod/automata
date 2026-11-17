"""Agente novo com defesas ligadas e memória fora de token de integração (ADR-0045).

Antes o agente nascia sem nenhuma defesa (LLM-01) e todos os usuários finais atrás de um
token de integração dividiam a mesma memória (LLM-02).
"""

import os
from collections.abc import Generator
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.factory import TOOL_RESULT_NOTICE, build_instructions, memory_owner
from app.repositories.config import ConfigRepository
from app.schemas.config import (
    SAFE_MAX_INPUT_CHARS,
    SAFE_TOOL_CALL_LIMIT,
    ConfigKind,
    ConfigPayload,
    GuardrailSettings,
    McpServerBinding,
)
from app.services.config import ConfigService
from app.settings import get_settings


@pytest.fixture(scope="module")
def svc() -> Generator[tuple[ConfigService, Session], None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        os.environ["DATABASE_URL"] = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.db import get_engine

        with Session(get_engine()) as session:
            yield ConfigService(ConfigRepository(session)), session
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _payload(data: dict[str, object]) -> ConfigPayload:
    return ConfigPayload.model_validate({"model_id": "gpt-4o", **data})


@pytest.mark.parametrize("kind", [ConfigKind.agent, ConfigKind.team])
def test_primeiro_rascunho_nasce_com_defesas(
    svc: tuple[ConfigService, Session], kind: ConfigKind
) -> None:
    service, session = svc
    config = service.create_config(f"novo-{kind}", "x", kind=kind)
    data: dict[str, object] = {}
    if kind == ConfigKind.team:
        member = service.create_config(f"membro-{uuid4()}", "x")
        service.save_draft(member.id, _payload({}), "autor")
        service.publish(member.id, "autor")
        data = {"team": {"members": [{"agent_id": str(member.id)}]}}
    draft = service.save_draft(config.id, _payload(data), "autor")
    session.commit()

    saved = ConfigPayload.model_validate(draft.payload)
    assert saved.guardrails.max_input_chars == SAFE_MAX_INPUT_CHARS
    assert saved.guardrails.tool_results is not None
    assert saved.guardrails.tool_results.terms
    assert saved.run.tool_call_limit == SAFE_TOOL_CALL_LIMIT

    # depois do primeiro, a seção que não vem fica como o schema manda
    segundo = ConfigPayload.model_validate(
        service.save_draft(config.id, _payload(data), "autor").payload
    )
    assert segundo.guardrails == GuardrailSettings()


def test_secao_mandada_no_primeiro_rascunho_e_respeitada(
    svc: tuple[ConfigService, Session],
) -> None:
    service, session = svc
    config = service.create_config("explicito", "x")
    draft = service.save_draft(
        config.id, _payload({"guardrails": {}, "run": {"tool_call_limit": 40}}), "autor"
    )
    session.commit()
    saved = ConfigPayload.model_validate(draft.payload)
    assert saved.guardrails.max_input_chars is None
    assert saved.run.tool_call_limit == 40


def test_frase_do_resultado_de_tool_so_com_mcp() -> None:
    sem = _payload({"instructions": {"objective": "atender"}})
    assert TOOL_RESULT_NOTICE not in (build_instructions(sem) or "")
    com = sem.model_copy(update={"mcp_servers": [McpServerBinding(server_id=uuid4())]})
    assert TOOL_RESULT_NOTICE in (build_instructions(com) or "")


@pytest.mark.parametrize(
    ("user_id", "owner"),
    [("u-1", "u-1"), ("integration:abc", None), (None, None)],
)
def test_memoria_nao_liga_para_token_de_integracao(user_id: str | None, owner: str | None) -> None:
    ctx = SimpleNamespace(user_id=user_id)
    assert memory_owner(ctx) == owner  # type: ignore[arg-type]


def test_numero_de_versao_e_unico_por_config(svc: tuple[ConfigService, Session]) -> None:
    import sqlalchemy.exc

    from app.models.config import AgentConfigVersion

    service, session = svc
    config = service.create_config("versoes", "x")
    first = service.save_draft(config.id, _payload({}), "autor")
    second = service.save_draft(config.id, _payload({}), "autor")
    session.commit()
    assert (first.version_number, second.version_number) == (1, 2)
    # dois editores no mesmo instante: o banco recusa o número repetido (OPS-11)
    session.add(
        AgentConfigVersion(
            config_id=config.id, version_number=2, status="draft", payload={}, author="outro"
        )
    )
    with pytest.raises(sqlalchemy.exc.IntegrityError):
        session.commit()
    session.rollback()
