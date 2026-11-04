"""Fila durável vista pelo owner e retry do agente idempotente (ADR-0037)."""

import os
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        os.environ["DATABASE_URL"] = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        os.environ["DEMO_REPLAY"] = "true"
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("DEMO_REPLAY", None)
        get_settings.cache_clear()


def _agent(client: TestClient, name: str, retries: int) -> str:
    agent_id = str(
        client.post("/api/v1/configs", json={"name": name, "description": "x"}).json()["id"]
    )
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": name,
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5", "run": {"background_retries": retries}},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    return agent_id


def _job(config_id: str, status: str, attempt: int = 1, age_s: int = 60) -> str:
    from app.job_queue import jobs_db

    db = jobs_db()
    db.ensure_jobs_table()
    table: Any = db._get_table(table_type="jobs")
    now = int(time.time())
    job_id = str(uuid4())
    with db.Session() as sess, sess.begin():
        sess.execute(
            table.insert().values(
                id=job_id,
                component_type="agent",
                job_type="run",
                component_id=config_id,
                session_id=str(uuid4()),
                payload={},
                status=status,
                attempt=attempt,
                max_attempts=attempt,
                available_at=now,
                error="ConnectError: provedor fora" if status == "failed" else None,
                created_at=now - age_s,
                updated_at=now - age_s,
                completed_at=now - age_s if status in ("failed", "completed") else None,
            )
        )
    return job_id


def test_fila_mostra_contagem_nome_e_requeue(client: TestClient) -> None:
    agent = _agent(client, "cobranca", 0)
    failed = _job(agent, "failed")
    done = _job(agent, "completed")
    _job(agent, "queued", age_s=300)

    data = client.get("/api/v1/queue").json()
    assert data["durable"] is True
    assert data["counts"]["failed"] >= 1 and data["counts"]["queued"] >= 1
    assert data["oldest_queued_at"] is not None
    [row] = [j for j in data["jobs"] if j["id"] == failed]
    assert row["component_name"] == "cobranca" and "provedor fora" in row["error"]

    assert client.post(f"/api/v1/queue/jobs/{failed}/requeue").status_code == 202
    [again] = [j for j in client.get("/api/v1/queue").json()["jobs"] if j["id"] == failed]
    assert again["status"] == "queued"
    assert client.post(f"/api/v1/queue/jobs/{done}/requeue").status_code == 409


def test_retry_do_agente_idempotente_e_aviso_de_falha(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.alerts as alerts
    from app.db import get_engine
    from app.job_queue import JOB_FAILED, check_jobs

    sent: list[str] = []
    monkeypatch.setattr(alerts, "destinations_for", lambda session, event: [object()])
    monkeypatch.setattr(alerts, "broadcast", lambda s, e, d, t: sent.append(t) or 1)

    idempotente = _agent(client, "consulta saldo", 1)
    comum = _agent(client, "paga boleto", 0)
    first_try = _job(idempotente, "failed", attempt=1)
    exhausted = _job(idempotente, "failed", attempt=2)
    no_retry = _job(comum, "failed", attempt=1)
    old = _job(comum, "failed", attempt=1, age_s=3 * 86400)

    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        result = dict(check_jobs(session, now))
        again = dict(check_jobs(session, now + timedelta(seconds=1)))
    assert result[first_try] == "requeued"
    assert result[exhausted] == JOB_FAILED and result[no_retry] == JOB_FAILED
    assert old not in result
    # o aviso sai uma vez por job
    assert exhausted not in again and no_retry not in again
    assert any("depois dos retries" in t for t in sent)
    assert any(t.startswith("Run em background de paga boleto falhou") for t in sent)


def test_fila_em_memoria_responde_desligada(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.job_queue as job_queue

    monkeypatch.setattr(job_queue, "durable", lambda: False)
    assert client.get("/api/v1/queue").json() == {
        "durable": False,
        "counts": {},
        "oldest_queued_at": None,
        "jobs": [],
    }
    assert client.post("/api/v1/queue/jobs/x/requeue").status_code == 409
