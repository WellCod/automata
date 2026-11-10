"""Trilha de auditoria (ADR-0041): o que entra, quem fez, o antes e o depois, e quem lê."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.audit import should_audit
from app.settings import get_settings

SECRET = "segredo-do-prompt-7781"


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/api/v1/configs/x/publish", True),
        ("PUT", "/api/v1/configs/x/draft", True),
        ("DELETE", "/api/v1/users/x", True),
        ("PATCH", "/api/v1/configs/x/canary", True),
        ("GET", "/api/v1/configs", False),
        ("POST", "/api/v1/auth/login", False),
        ("POST", "/api/v1/auth/logout", False),
        ("POST", "/api/v1/linter", False),
        ("POST", "/api/v1/knowledge-bases/x/search", False),
        ("POST", "/api/v1/knowledge-bases/x/search/compare", False),
        ("POST", "/api/v1/knowledge-bases/x/chunk-preview", False),
        ("POST", "/api/v1/knowledge-connectors/x/webhook", False),
        # a rota do painel que gera o segredo do webhook é escrita
        ("PUT", "/api/v1/knowledge-connectors/x/webhook", True),
        ("POST", "/agents/a/runs/r/continue", True),
        ("POST", "/workflows/w/runs/r/continue", True),
        ("POST", "/agents/a/runs", False),
    ],
)
def test_o_que_entra_na_trilha(method: str, path: str, expected: bool) -> None:
    assert should_audit(method, path) is expected


def _pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    private, public = _pair()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": private,
            "JWT_PUBLIC_KEY": public,
            "DEMO_REPLAY": "true",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
        with TestClient(app) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _h(sub: str, scopes: list[str]) -> dict[str, str]:
    from app.auth import issue_token

    return {"Authorization": f"Bearer {issue_token(sub, scopes)}"}


OWNER = ["agent_os:admin"]


def _viewer() -> list[str]:
    from app.models.user import UserRole
    from app.schemas.user import ROLE_SCOPES

    return list(ROLE_SCOPES[UserRole.viewer])


def _events(config_id: str | None = None) -> list[dict[str, object]]:
    from app.db import get_engine
    from app.models.audit import AuditEvent

    with Session(get_engine()) as session:
        query = select(AuditEvent).order_by(AuditEvent.created_at)
        if config_id:
            query = query.where(AuditEvent.config_id == config_id)
        return [
            {
                "actor": e.actor,
                "action": e.action,
                "status": e.status_code,
                "params": e.params,
                "detail": e.detail,
                "request_id": e.request_id,
            }
            for e in session.scalars(query)
        ]


def _agent(client: TestClient, name: str) -> str:
    owner = _h("owner", OWNER)
    config_id = client.post(
        "/api/v1/configs", json={"name": name, "description": "x"}, headers=owner
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={
            "name": name,
            "description": "x",
            "payload": {"model_id": "gpt-4o", "instructions": {"objective": SECRET}},
        },
        headers=owner,
    ).raise_for_status()
    return str(config_id)


def test_publicacao_com_antes_e_depois_e_sem_corpo(client: TestClient) -> None:
    owner = _h("owner", OWNER)
    agent = _agent(client, "auditado")
    published = client.post(f"/api/v1/configs/{agent}/publish", headers=owner)
    assert published.status_code == 201, published.text
    client.get(f"/api/v1/configs/{agent}", headers=owner)

    events = _events(agent)
    assert [e["action"] for e in events] == [
        "PUT /api/v1/configs/{config_id}/draft",
        "POST /api/v1/configs/{config_id}/publish",
    ]
    publish = events[1]
    assert publish["actor"] == "owner"
    assert publish["status"] == 201
    assert publish["request_id"]
    detail = publish["detail"]
    assert isinstance(detail, dict)
    assert detail["current_before"] is None
    assert detail["current_after"] == published.json()["id"]

    from app.db import get_engine

    with Session(get_engine()) as session:
        dump = session.execute(text("SELECT string_agg(audit_event::text, '|') FROM audit_event"))
        assert SECRET not in (dump.scalar() or "")


def test_escrita_negada_entra_com_o_status(client: TestClient) -> None:
    agent = _agent(client, "negado")
    denied = client.post(f"/api/v1/configs/{agent}/publish", headers=_h("visitante", _viewer()))
    assert denied.status_code == 403
    last = _events(agent)[-1]
    assert last["actor"] == "visitante"
    assert last["status"] == 403


def test_rollback_canario_e_piso_guardam_o_antes_e_o_depois(client: TestClient) -> None:
    owner = _h("owner", OWNER)
    agent = _agent(client, "produção")
    v1 = client.post(f"/api/v1/configs/{agent}/publish", headers=owner).json()["id"]
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={"name": "p", "description": "x", "payload": {"model_id": "gpt-4o"}},
        headers=owner,
    ).raise_for_status()
    v2 = client.post(f"/api/v1/configs/{agent}/publish", headers=owner).json()["id"]
    client.post(
        f"/api/v1/configs/{agent}/rollback", json={"version_id": v1}, headers=owner
    ).raise_for_status()
    client.post(
        f"/api/v1/configs/{agent}/canary", json={"percent": 10, "version_id": v2}, headers=owner
    ).raise_for_status()
    client.patch(
        f"/api/v1/configs/{agent}/canary", json={"percent": 30}, headers=owner
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/canary/promote", headers=owner).raise_for_status()

    by_action = {str(e["action"]): e["detail"] for e in _events(agent)}
    assert by_action["POST /api/v1/configs/{config_id}/rollback"] == {
        "current_before": v2,
        "current_after": v1,
    }
    assert by_action["POST /api/v1/configs/{config_id}/canary"] == {
        "canary_version": v2,
        "percent": 10,
        "from_draft": False,
    }
    assert by_action["PATCH /api/v1/configs/{config_id}/canary"] == {
        "percent_before": 10,
        "percent_after": 30,
    }
    assert by_action["POST /api/v1/configs/{config_id}/canary/promote"] == {
        "current_before": v1,
        "current_after": v2,
    }

    floor = {"settings": {"max_input_chars": 4000}}
    put = client.put("/api/v1/instance-guardrails", json=floor, headers=owner)
    assert put.status_code == 200, put.text
    floor_event = [e for e in _events() if e["action"] == "PUT /api/v1/instance-guardrails"][-1]
    detail = floor_event["detail"]
    assert isinstance(detail, dict)
    assert detail["before"] is None
    assert detail["after"]["max_input_chars"] == 4000


def test_titular_entra_como_pseudonimo(client: TestClient) -> None:
    from app.data_subjects import pseudonym

    owner = _h("owner", OWNER)
    resp = client.post("/api/v1/data-subjects/cliente-99/export", headers=owner)
    assert resp.status_code == 202, resp.text
    event = [e for e in _events() if "/data-subjects/" in str(e["action"])][-1]
    assert event["params"] == {"user_id": pseudonym("cliente-99")}


def test_so_o_owner_le_com_filtro_e_cursor(client: TestClient) -> None:
    owner = _h("owner", OWNER)
    agent = _agent(client, "leitura")
    client.post(f"/api/v1/configs/{agent}/publish", headers=owner).raise_for_status()

    assert client.get("/api/v1/audit", headers=_h("visitante", _viewer())).status_code == 403

    first = client.get(
        "/api/v1/audit", params={"config_id": agent, "limit": 1}, headers=owner
    ).json()
    assert len(first["items"]) == 1
    assert first["items"][0]["action"].endswith("/publish")
    assert first["next_cursor"]
    assert first["configs"][agent] == {"name": "leitura", "kind": "agent"}
    after = first["items"][0]["detail"]["current_after"]
    assert first["versions"][after] == 2
    second = client.get(
        "/api/v1/audit",
        params={"config_id": agent, "limit": 1, "cursor": first["next_cursor"]},
        headers=owner,
    ).json()
    assert second["items"][0]["action"].endswith("/draft")
    assert second["next_cursor"] is None

    by_actor = client.get("/api/v1/audit", params={"actor": "visitante"}, headers=owner).json()
    assert by_actor["items"]
    assert all(i["actor"] == "visitante" for i in by_actor["items"])
    assert client.get("/api/v1/audit", params={"cursor": "lixo"}, headers=owner).status_code == 422


def test_retencao_e_exclusao_do_titular(client: TestClient) -> None:
    from app.audit import forget_subject, purge, record
    from app.db import get_engine
    from app.models.audit import AuditEvent

    record(
        actor="pessoa-1",
        action="PATCH /api/v1/users/{user_id}",
        params={"user_id": "pessoa-1"},
        status_code=200,
        ip="10.0.0.1",
        request_id="r1",
        detail=None,
    )
    with Session(get_engine()) as session:
        assert forget_subject(session, "pessoa-1", "anon-1") == 2
        session.commit()
        row = session.scalars(select(AuditEvent).where(AuditEvent.actor == "anon-1")).one()
        assert row.params == {"user_id": "anon-1"}

        row.created_at = datetime.now(UTC) - timedelta(days=400)
        session.commit()
        assert purge(session, datetime.now(UTC), days=365) == 1
        assert (
            session.scalars(select(AuditEvent).where(AuditEvent.actor == "anon-1")).first() is None
        )
