"""Orçamento mensal por config (ADR-0021): gasto do mês, nível e bloqueio antes do run."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel


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
    import app.budget as budget
    from app.main import create_app

    # sem o cache de 30 s, cada run lê o gasto que o anterior acabou de gravar
    monkeypatch.setattr(budget, "CACHE_S", 0.0)
    # 1.000 tokens de saída do haiku: US$ 0,005 por run, pela tabela de preços
    model = FixedReplyModel(id="claude-haiku-4-5", reply="ok", tokens=1_000)
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _agent(client: TestClient, name: str) -> str:
    config_id = client.post(
        "/api/v1/configs", json={"name": name, "description": "x", "kind": "agent"}
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": name, "description": "x", "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _run(client: TestClient, agent: str) -> str:
    resp = client.post(f"/agents/{agent}/runs", data={"message": "oi", "stream": "false"})
    resp.raise_for_status()
    return str(resp.json()["content"])


def test_sem_orcamento_so_mostra_o_gasto(client: TestClient) -> None:
    agent = _agent(client, "sem orçamento")
    _run(client, agent)
    got = client.get(f"/api/v1/configs/{agent}/budget").json()
    assert got["monthly_usd"] is None
    assert got["level"] is None
    assert got["spent_usd"] == pytest.approx(0.005)


def test_estouro_com_bloqueio_barra_o_run_seguinte_sem_chamar_o_modelo(
    client: TestClient,
) -> None:
    from app.budget import BUDGET_MESSAGE

    agent = _agent(client, "com orçamento")
    put = client.put(
        f"/api/v1/configs/{agent}/budget",
        json={"monthly_usd": 0.01, "alert_percent": 50, "hard_stop": True},
    )
    assert put.status_code == 200, put.text
    assert put.json()["level"] == "ok"

    assert _run(client, agent) == "ok"
    assert client.get(f"/api/v1/configs/{agent}/budget").json()["level"] == "warning"
    assert _run(client, agent) == "ok"
    state = client.get(f"/api/v1/configs/{agent}/budget").json()
    assert state["level"] == "exceeded"
    assert state["percent"] == pytest.approx(100)

    assert _run(client, agent) == BUDGET_MESSAGE
    runs = client.get(f"/api/v1/configs/{agent}/runs").json()["items"]
    assert runs[0]["status"] == "blocked"
    assert runs[0]["blocked_by"] == "budget_exceeded"
    # o run barrado não chamou o modelo: o gasto não andou
    assert client.get(f"/api/v1/configs/{agent}/budget").json()["spent_usd"] == pytest.approx(0.01)

    # sem o bloqueio, o orçamento só avisa
    client.put(
        f"/api/v1/configs/{agent}/budget",
        json={"monthly_usd": 0.01, "alert_percent": 50, "hard_stop": False},
    ).raise_for_status()
    assert _run(client, agent) == "ok"


def test_orcamento_invalido_e_recusado(client: TestClient) -> None:
    agent = _agent(client, "orçamento inválido")
    for body in ({"monthly_usd": 0}, {"monthly_usd": -1}, {"monthly_usd": 5, "alert_percent": 100}):
        assert client.put(f"/api/v1/configs/{agent}/budget", json=body).status_code == 422
