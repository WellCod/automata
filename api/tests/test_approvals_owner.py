"""Aprovações pendentes: cada usuário vê as dele, o owner vê todas (Fase 28)."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


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


def test_viewer_ve_so_as_proprias_pendencias(client: TestClient) -> None:
    from app.db import get_engine
    from app.models.run import AgentRun
    from app.schemas.user import ROLE_SCOPES, UserRole

    owner = _h("owner", ["agent_os:admin"])
    config = {"name": "loja", "description": "Use para loja"}
    agent_id = client.post("/api/v1/configs", json=config, headers=owner).json()["id"]
    tool = {"tool_call_id": "c1", "tool_name": "estornar", "tool_args": {"valor": 120}}
    with Session(get_engine()) as session:
        for user in ("ana", "bruno"):
            session.add(
                AgentRun(
                    agent_config_id=agent_id,
                    user_id=user,
                    run_id=f"run-{user}",
                    session_id=f"s-{user}",
                    status="paused",
                    pending_tools=[tool],
                )
            )
        session.commit()

    viewer = ROLE_SCOPES[UserRole.viewer]
    seen = client.get("/api/v1/approvals", headers=_h("ana", viewer))
    assert seen.status_code == 200, seen.text
    assert [i["user_id"] for i in seen.json()] == ["ana"]

    editor = ROLE_SCOPES[UserRole.editor]
    assert client.get("/api/v1/approvals", headers=_h("carla", editor)).json() == []

    everyone = client.get("/api/v1/approvals", headers=owner).json()
    assert sorted(i["user_id"] for i in everyone) == ["ana", "bruno"]
