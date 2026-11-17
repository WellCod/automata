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
def client() -> Generator[TestClient]:
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


def test_modelo_extra_pelo_ambiente(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.extra_models import _parse
    from app.agents.models_map import resolve_model
    from app.pricing import prices

    _parse.cache_clear()
    monkeypatch.setenv(
        "EXTRA_MODELS",
        '[{"id": "azure-gpt-4o", "provider": "openai", "model": "gpt-4o",'
        ' "base_url": "https://empresa.openai.azure.com/openai/v1",'
        ' "api_key_env": "AZURE_OPENAI_KEY", "vision": true,'
        ' "input_price": 2.5, "output_price": 10}]',
    )
    monkeypatch.setenv("AZURE_OPENAI_KEY", "az-teste")
    caps = client.get("/api/v1/models/capabilities").json()
    assert caps["azure-gpt-4o"]["vision"] is True
    assert client.get("/api/v1/models/availability").json()["azure-gpt-4o"] is True
    model = resolve_model("azure-gpt-4o")
    assert model.id == "gpt-4o" and str(model.base_url).startswith("https://empresa")  # type: ignore[attr-defined]
    assert prices()["azure-gpt-4o"].input == 2.5
    # o rascunho aceita o modelo extra
    config_id = client.post("/api/v1/configs", json={"name": "azure", "description": "x"}).json()[
        "id"
    ]
    draft = client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": "azure", "description": "x", "payload": {"model_id": "azure-gpt-4o"}},
    )
    assert draft.status_code == 201, draft.text
    monkeypatch.setenv("EXTRA_MODELS", "isto não é json")
    assert "azure-gpt-4o" not in client.get("/api/v1/models/capabilities").json()


def test_marca_e_moeda_da_instancia(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.settings import get_settings

    monkeypatch.setenv("APP_NAME", "Agentes Cliente")
    monkeypatch.setenv("APP_LOGO_URL", "https://cdn.exemplo.com/logo.png")
    monkeypatch.setenv("BRL_PER_USD", "5.4")
    get_settings.cache_clear()
    try:
        info = client.get("/api/v1/auth/instance").json()
        # logo de outro domínio a CSP do painel bloquearia: fica o padrão
        assert info == {"app_name": "Agentes Cliente", "app_logo": None, "brl_per_usd": 5.4}
    finally:
        get_settings.cache_clear()
