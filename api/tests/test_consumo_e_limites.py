"""Consumo em CSV, limites do plano e filtro das execuções (COM-06, UX-07)."""

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
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
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        patch.undo()
        get_settings.cache_clear()


def test_consumo_do_mes_em_csv_sem_id_de_quem_usou(client: TestClient) -> None:
    from app.db import get_engine
    from app.models.usage import UsageEvent

    config_id = client.post(
        "/api/v1/configs", json={"name": "=Cobrança", "description": "x"}
    ).json()["id"]
    period = datetime.now(UTC).strftime("%Y%m")
    with Session(get_engine()) as session:
        for run in ("r1", "r2"):
            session.add(
                UsageEvent(
                    agent_config_id=config_id,
                    user_id="whatsapp:5511999990000",
                    run_id=run,
                    model_id="gpt-4o",
                    period=period,
                    input_tokens=10,
                    output_tokens=5,
                    total_tokens=15,
                    cost=0.002,
                )
            )
        session.commit()

    resp = client.get("/api/v1/usage/export", params={"period": period})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    text = resp.content.decode("utf-8-sig")
    header, row = text.strip().splitlines()
    assert header.startswith("data;agente;modelo")
    cells = row.split(";")
    assert cells[1] == "'=Cobrança" and cells[2] == "gpt-4o" and cells[3] == "2"
    assert cells[6] == "30" and cells[7] == "0.004000"
    assert "5511999990000" not in text


def test_limite_de_agentes_do_plano(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAN_MAX_CONFIGS", "1")
    get_settings.cache_clear()
    try:
        resp = client.post("/api/v1/configs", json={"name": "mais um", "description": "x"})
        assert resp.status_code == 409 and "plano" in resp.json()["detail"]
    finally:
        monkeypatch.delenv("PLAN_MAX_CONFIGS")
        get_settings.cache_clear()


def test_execucoes_filtradas_por_status_e_periodo(client: TestClient) -> None:
    from app.db import get_engine
    from app.models.run import AgentRun

    config_id = client.post("/api/v1/configs", json={"name": "filtro", "description": "x"}).json()[
        "id"
    ]
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        for status, age in (("success", 1), ("error", 1), ("error", 40)):
            session.add(
                AgentRun(
                    agent_config_id=config_id,
                    user_id="u",
                    status=status,
                    duration_ms=10,
                    created_at=now - timedelta(days=age),
                )
            )
        session.commit()
    url = f"/api/v1/configs/{config_id}/runs"
    assert client.get(url).json()["total"] == 3
    assert client.get(url, params={"status": "error"}).json()["total"] == 2
    since = (now - timedelta(days=7)).isoformat()
    assert client.get(url, params={"status": "error", "since": since}).json()["total"] == 1
