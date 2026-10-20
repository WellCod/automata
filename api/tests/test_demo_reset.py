"""Reset da demo apaga runs, uso e os dados do Agno (sessões, memórias, traces)."""

import importlib.util
import os
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest
from agno.db.postgres import PostgresDb
from agno.db.schemas.memory import UserMemory
from agno.session.agent import AgentSession
from alembic.config import Config
from sqlalchemy import Engine, create_engine, func, select, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.models.user import User
from app.seed import seed_analytics, seed_demo
from app.settings import get_settings


def _load_script() -> ModuleType:
    path = Path(__file__).parent.parent / "scripts" / "demo_reset.py"
    spec = importlib.util.spec_from_file_location("demo_reset", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def engine() -> Generator[Engine, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        previous = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        eng = create_engine(url)
        yield eng
        eng.dispose()
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _count(engine: Engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one())


def test_reset_limpa_runs_e_tabelas_do_agno(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@demo.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "Senha123!")
    with Session(engine) as session:
        seed_demo(session)
        seed_analytics(session, n_runs=5)

    agno = PostgresDb(db_url=engine.url.render_as_string(hide_password=False))
    agno.upsert_session(AgentSession(session_id="s1", agent_id="a1", user_id="u1", created_at=1))
    agno.upsert_user_memory(UserMemory(memory="gosta de tabelas", user_id="u1"))
    agno._get_table("traces", create_table_if_not_found=True)
    agno._get_table("spans", create_table_if_not_found=True)
    assert _count(engine, 'ai."agno_sessions"') == 1
    assert _count(engine, 'ai."agno_memories"') == 1

    truncated = _load_script().truncate_all(engine)

    assert 'ai."agno_traces"' in truncated
    assert 'ai."agno_spans"' in truncated
    # tabela que o Agno ainda não criou não entra (TRUNCATE falharia)
    assert 'ai."agno_culture"' not in truncated
    assert _count(engine, 'ai."agno_sessions"') == 0
    assert _count(engine, 'ai."agno_memories"') == 0
    with Session(engine) as session:
        for model in (AgentRun, UsageEvent, User):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_seed_cria_base_de_exemplo_e_reset_apaga_vetores(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.knowledge import demo_content
    from app.models.config import AgentConfig, AgentConfigVersion
    from app.models.knowledge_base import KnowledgeBase
    from app.models.knowledge_content import KnowledgeContent

    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@demo.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "Senha123!")
    # embedder local: o seed da demo roda sem chave
    monkeypatch.setenv("DEMO_REPLAY", "true")
    with Session(engine) as session:
        seed_demo(session)
        seed_demo(session)  # idempotente

    with Session(engine) as session:
        [base] = session.scalars(select(KnowledgeBase)).all()
        contents = session.scalars(select(KnowledgeContent)).all()
        assert {c.name for c in contents} == set(demo_content.DOCUMENTS)
        assert all(c.status == "completed" for c in contents)
        agent = session.scalars(
            select(AgentConfig).where(AgentConfig.name == "Atendimento ao Cliente")
        ).one()
        version = session.get(AgentConfigVersion, agent.current_version_id)
        assert version is not None
        assert version.payload["knowledge"][0]["base_id"] == str(base.id)
        table = base.vector_table

    truncated = _load_script().truncate_all(engine)

    assert f'ai."{table}"' in truncated
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass(:t)"), {"t": f"ai.{table}"}).scalar() is None
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(KnowledgeBase)) == 0


def test_seed_cria_workflow_de_exemplo_sem_runs_falsos(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models.config import AgentConfig, AgentConfigVersion
    from app.schemas.workflow import WorkflowSettings, step_nodes

    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@demo.com")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "Senha123!")
    with Session(engine) as session:
        seed_demo(session)
        seed_demo(session)  # idempotente
        seed_analytics(session, n_runs=50)

    with Session(engine) as session:
        [workflow] = session.scalars(
            select(AgentConfig).where(AgentConfig.kind == "workflow")
        ).all()
        version = session.get(AgentConfigVersion, workflow.current_version_id)
        assert version is not None
        settings = WorkflowSettings.model_validate(version.payload["workflow"])
        agents = {
            a.id: a.name
            for a in session.scalars(select(AgentConfig).where(AgentConfig.kind == "agent"))
        }
        assert [(s.name, agents[s.agent_id]) for s in step_nodes(settings.steps)] == [  # type: ignore[index]
            ("triagem", "Atendimento ao Cliente"),
            ("técnica", "Suporte Técnico"),
            ("financeira", "Analista Financeiro"),
            ("consolidação", "Atendimento ao Cliente"),
            ("revisão", "Analista Financeiro"),
        ]
        # workflow não ganha runs nem consumo inventados: o dele é a soma das etapas
        for model in (AgentRun, UsageEvent):
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.agent_config_id == workflow.id)
                )
                == 0
            )
        assert session.scalar(select(func.count()).select_from(AgentRun)) == 50
