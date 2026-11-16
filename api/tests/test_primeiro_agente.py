"""Primeiro agente sem ajuda: modelos de exemplo e modelos sem chave (UX-02, UX-03)."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        patch = pytest.MonkeyPatch()
        patch.setenv("DATABASE_URL", pg.get_connection_url().replace("psycopg2", "psycopg"))
        patch.setenv("JWT_PRIVATE_KEY", "x")
        patch.setenv("JWT_PUBLIC_KEY", "x")
        patch.delenv("DEMO_REPLAY", raising=False)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        patch.undo()
        get_settings.cache_clear()


def test_cria_agente_a_partir_de_modelo_com_defesas(client: TestClient) -> None:
    templates = client.get("/api/v1/templates").json()
    keys = {t["key"] for t in templates}
    assert "atendimento-ao-cliente" in keys

    created = client.post("/api/v1/templates/atendimento-ao-cliente")
    assert created.status_code == 201, created.text
    config = client.get(f"/api/v1/configs/{created.json()['id']}").json()
    payload = config["payload"]
    assert payload["instructions"]["persona"]
    assert payload["run"]["tool_call_limit"] == 15
    assert payload["guardrails"]["max_input_chars"] == 20000
    assert client.post("/api/v1/templates/nao-existe").status_code == 404


def test_modelo_sem_chave_do_provedor(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    available = client.get("/api/v1/models/availability").json()
    assert available["claude-haiku-4-5"] is True
    assert available["gpt-4o"] is False
    assert os.environ.get("OPENAI_API_KEY") is None
