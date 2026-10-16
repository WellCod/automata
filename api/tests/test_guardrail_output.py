"""Guardrail de saída (ADR-0013): resposta trocada no não-stream, run marcado no stream."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from agno.exceptions import OutputCheckError
from agno.models.message import Message
from agno.run.agent import RunOutput
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.guardrails.input import BlockLog
from app.guardrails.output import RULE_OUTPUT, output_guardrail
from app.models.run import AgentRun
from app.schemas.config import GuardrailSettings, OutputRule
from app.settings import get_settings

CPF = "529.982.247-25"


def test_desligado_por_padrao() -> None:
    assert output_guardrail(GuardrailSettings()) is None


def test_troca_resposta_e_mensagem_gravada() -> None:
    log = BlockLog()
    hook = output_guardrail(
        GuardrailSettings(output=OutputRule(pii=True), blocked_message="Resposta retida."), log
    )
    assert hook is not None
    out = RunOutput(
        content=f"O CPF do cliente é {CPF}",
        messages=[
            Message(role="user", content="qual o cpf?"),
            Message(role="assistant", content=f"O CPF do cliente é {CPF}"),
        ],
    )
    with pytest.raises(OutputCheckError):
        hook(run_output=out)
    assert out.content == "Resposta retida."
    assert out.messages is not None
    assert out.messages[1].content == "Resposta retida."
    assert out.messages[0].content == "qual o cpf?"
    assert log.last is not None
    assert (log.last.rule, log.last.detail) == (RULE_OUTPUT, {"types": ["cpf"]})


def test_termo_proibido_na_resposta() -> None:
    hook = output_guardrail(GuardrailSettings(output=OutputRule(blocked_terms=["Concorrente X"])))
    assert hook is not None
    hook(run_output=RunOutput(content="Nosso plano custa R$ 50."))
    with pytest.raises(OutputCheckError):
        hook(run_output=RunOutput(content="O concorrente x é mais barato"))


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app
    from tests.fake_models import FixedReplyModel

    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    model = FixedReplyModel(id="claude-haiku-4-5", reply=f"Claro! O CPF cadastrado é {CPF}.")
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _agente(client: TestClient) -> str:
    agent_id = client.post("/api/v1/configs", json={"name": "saida", "description": "x"}).json()[
        "id"
    ]
    guardrails: dict[str, Any] = {
        "output": {"pii": True},
        "blocked_message": "Não posso compartilhar esse dado.",
    }
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "saida",
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5", "guardrails": guardrails},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    return str(agent_id)


def test_nao_stream_entrega_mensagem_de_bloqueio_e_nao_grava_o_dado(client: TestClient) -> None:
    agent_id = _agente(client)
    resp = client.post(
        f"/agents/{agent_id}/runs",
        data={"message": "qual o cpf do cliente?", "stream": "false", "session_id": "s-out"},
    )
    body = resp.json()
    assert body["status"] == "ERROR"
    assert body["content"] == "Não posso compartilhar esse dado."
    assert CPF not in resp.text

    with get_engine().connect() as conn:
        stored = conn.execute(
            text("SELECT runs::text FROM ai.agno_sessions WHERE session_id = 's-out'")
        ).scalar_one()
    assert CPF not in stored

    with Session(get_engine()) as session:
        run = session.scalars(select(AgentRun).where(AgentRun.agent_config_id == agent_id)).one()
    assert (run.status, run.blocked_by, run.block_detail) == (
        "blocked",
        RULE_OUTPUT,
        {"types": ["cpf"]},
    )


def test_stream_marca_o_run_depois_do_texto(client: TestClient) -> None:
    agent_id = _agente(client)
    resp = client.post(
        f"/agents/{agent_id}/runs", data={"message": "qual o cpf?", "stream": "true"}
    )
    # limite registrado no ADR: no stream o texto já saiu quando a saída é validada
    assert "RunError" in resp.text
    with Session(get_engine()) as session:
        run = session.scalars(select(AgentRun).where(AgentRun.agent_config_id == agent_id)).one()
    assert (run.status, run.blocked_by) == ("blocked", RULE_OUTPUT)
