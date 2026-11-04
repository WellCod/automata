"""Direitos do titular (ADR-0032): consulta e exportação isoladas por titular."""

import gzip
import json
import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.settings import get_settings

ANA = "ana@cliente.com"
BIA = "bia@cliente.com"


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


@pytest.fixture(scope="module")
def client(db_url: str) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app

    patch = pytest.MonkeyPatch()
    patch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    model = ReplayModel(id="claude-haiku-4-5")
    patch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        _seed(c, db_url)
        yield c
    patch.undo()


def _seed(client: TestClient, db_url: str) -> None:
    from agno.db.postgres import PostgresDb
    from agno.db.schemas.memory import UserMemory

    created = client.post("/api/v1/configs", json={"name": "atendimento", "description": "x"})
    agent_id = created.json()["id"]
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "atendimento",
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5"},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    for user, message in ((ANA, "pedido 111 da ana"), (BIA, "pedido 222 da bia")):
        resp = client.post(
            f"/agents/{agent_id}/runs",
            data={"message": message, "stream": "false", "user_id": user},
        )
        assert resp.status_code == 200, resp.text
    db = PostgresDb(db_url=db_url)
    db.upsert_user_memory(UserMemory(memory="ana prefere entrega à tarde", user_id=ANA))
    db.upsert_user_memory(UserMemory(memory="bia mora em Recife", user_id=BIA))


def test_consulta_conta_so_o_que_e_do_titular(client: TestClient) -> None:
    ana = client.get(f"/api/v1/data-subjects/{ANA}").json()
    assert ana["counts"]["sessions"] == 1 and ana["counts"]["runs"] >= 1
    assert ana["counts"]["memories"] == 1 and ana["counts"]["agent_runs"] == 1
    assert ana["total"] == sum(ana["counts"].values())
    nobody = client.get("/api/v1/data-subjects/ninguem@exemplo.com").json()
    assert nobody["total"] == 0


def test_exportacao_traz_o_titular_e_nada_de_outro(client: TestClient) -> None:
    resp = client.post(f"/api/v1/data-subjects/{ANA}/export")
    assert resp.status_code == 202, resp.text
    request_id = resp.json()["id"]
    [row] = [r for r in client.get("/api/v1/data-subject-requests").json() if r["id"] == request_id]
    assert row["status"] == "done", row["error"]
    assert row["subject"] == ANA and row["counts"]["memories"] == 1

    download = client.get(f"/api/v1/data-subject-requests/{request_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/gzip"
    assert "no-store" in download.headers["cache-control"]
    data: dict[str, Any] = json.loads(gzip.decompress(download.content))
    text = json.dumps(data, ensure_ascii=False)
    assert "pedido 111 da ana" in text and "entrega à tarde" in text
    assert "pedido 222" not in text and "Recife" not in text and BIA not in text
    assert {s["user_id"] for s in data["agno"]["sessions"]} == {ANA}
    assert data["agent_runs"] and data["usage"] is not None


def test_arquivo_vencido_sai_com_o_id_em_claro(client: TestClient) -> None:
    from app.db import get_engine
    from app.models.data_subject import DataSubjectRequest

    request_id = client.post(f"/api/v1/data-subjects/{BIA}/export").json()["id"]
    with Session(get_engine()) as session:
        session.execute(
            update(DataSubjectRequest)
            .where(DataSubjectRequest.id == request_id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        session.commit()
    [row] = [r for r in client.get("/api/v1/data-subject-requests").json() if r["id"] == request_id]
    assert (row["status"], row["subject"]) == ("expired", None)
    assert len(row["subject_hash"]) == 64
    assert client.get(f"/api/v1/data-subject-requests/{request_id}/download").status_code == 409
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/data-subject-requests/{missing}/download").status_code == 404


# --- exclusão ---


def _agent_id(client: TestClient) -> str:
    [config] = [
        c for c in client.get("/api/v1/configs").json()["items"] if c["name"] == "atendimento"
    ]
    return str(config["id"])


def test_confirmacao_errada_nao_apaga(client: TestClient) -> None:
    resp = client.post(f"/api/v1/data-subjects/{ANA}/erase", json={"confirm": "ana"})
    assert resp.status_code == 422
    assert client.get(f"/api/v1/data-subjects/{ANA}").json()["total"] > 0


def test_exclusao_apaga_o_titular_e_mantem_metricas_e_outro(client: TestClient) -> None:
    from sqlalchemy import func, select

    from app.data_subjects import pseudonym, subject_hash
    from app.db import get_engine
    from app.models.run import AgentRun
    from app.models.usage import UsageEvent

    agent_id = _agent_id(client)
    before = client.get(f"/api/v1/configs/{agent_id}/metrics").json()
    bia_before = client.get(f"/api/v1/data-subjects/{BIA}").json()["counts"]

    resp = client.post(f"/api/v1/data-subjects/{ANA}/erase", json={"confirm": ANA})
    assert resp.status_code == 202, resp.text
    request_id = resp.json()["id"]
    assert resp.json()["subject"] is None

    assert client.get(f"/api/v1/data-subjects/{ANA}").json()["total"] == 0
    assert client.get(f"/api/v1/data-subjects/{BIA}").json()["counts"] == bia_before
    after = client.get(f"/api/v1/configs/{agent_id}/metrics").json()
    assert after["total_runs"] == before["total_runs"]

    with Session(get_engine()) as session:
        alias = pseudonym(ANA)
        assert session.scalar(select(func.count()).where(AgentRun.user_id == alias)) == 1
        kept = session.scalar(select(func.count()).where(UsageEvent.user_id == alias))
        assert kept is not None and kept >= 0

    rows = client.get("/api/v1/data-subject-requests").json()
    [row] = [r for r in rows if r["id"] == request_id]
    assert (row["kind"], row["status"], row["subject"]) == ("erase", "done", None)
    assert row["subject_hash"] == subject_hash(ANA)
    assert row["counts"]["sessions"] == 1 and row["counts"]["memories"] == 1
    assert ANA not in json.dumps(rows)
