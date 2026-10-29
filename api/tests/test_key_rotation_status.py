"""Estado da rotação (ADR-0026): tokens de integração e segredos que dependem da chave anterior."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
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


_OLD, _NEW = _pair(), _pair()
_OLD_FERNET, _NEW_FERNET = Fernet.generate_key().decode(), Fernet.generate_key().decode()
_VARS = (
    "DATABASE_URL",
    "JWT_PRIVATE_KEY",
    "JWT_PUBLIC_KEY",
    "JWT_PREVIOUS_PUBLIC_KEY",
    "MCP_SECRETS_KEY",
    "MCP_SECRETS_PREVIOUS_KEY",
    "MCP_ALLOWED_HOSTS",
    "DEMO_REPLAY",
)


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    old = {k: os.environ.get(k) for k in _VARS}
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        _set(url, jwt=_OLD, fernet=_OLD_FERNET)
        command.upgrade(Config("alembic.ini"), "head")
        yield url
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    get_settings.cache_clear()


def _set(
    url: str,
    *,
    jwt: tuple[str, str],
    fernet: str,
    previous_jwt: str = "",
    previous_fernet: str = "",
) -> None:
    os.environ.update(
        {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": jwt[0],
            "JWT_PUBLIC_KEY": jwt[1],
            "JWT_PREVIOUS_PUBLIC_KEY": previous_jwt,
            "MCP_SECRETS_KEY": fernet,
            "MCP_SECRETS_PREVIOUS_KEY": previous_fernet,
            "MCP_ALLOWED_HOSTS": "127.0.0.1",
            "DEMO_REPLAY": "true",
        }
    )
    get_settings.cache_clear()


def _client() -> TestClient:
    from app.main import create_app

    app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
    return TestClient(app)


def _h(scopes: list[str]) -> dict[str, str]:
    from app.auth import issue_token

    return {"Authorization": f"Bearer {issue_token('owner', scopes)}"}


def _status(client: TestClient) -> dict[str, Any]:
    resp = client.get("/api/v1/key-rotation", headers=_h(["agent_os:admin"]))
    assert resp.status_code == 200, resp.text
    body: dict[str, Any] = resp.json()
    return body


def test_rotacao_completa_do_estado(db_url: str) -> None:
    from app.auth import key_id
    from app.db import get_engine
    from app.models.integration import IntegrationToken
    from app.rotate_secrets import main as rotate_secrets

    owner = ["agent_os:admin"]
    with _client() as client:
        config = {"name": "crm", "description": "Use para crm"}
        agent_id = client.post("/api/v1/configs", json=config, headers=_h(owner)).json()["id"]
        issued = client.post(
            "/api/v1/integrations",
            json={"name": "sistema", "eval_ids": [agent_id], "expires_in_days": 7},
            headers=_h(owner),
        )
        assert issued.status_code == 201, issued.text
        old_token = issued.json()["token"]
        assert issued.json()["on_current_key"] is True
        server = client.post(
            "/api/v1/mcp-servers",
            json={
                "name": "CRM",
                "slug": "crm",
                "url": "http://127.0.0.1:9/mcp",
                "headers": {"Authorization": "Bearer segredo"},
            },
            headers=_h(owner),
        )
        assert server.status_code == 201, server.text
        status = _status(client)
        assert status["jwt"]["current_kid"] == key_id(_OLD[1])
        assert status["secrets"]["pending"]["mcp_server"] == 0
        assert status["done"] is True
        # editor não vê o estado das chaves
        editor = ["configs:read", "configs:write", "configs:publish", "evals:run"]
        assert client.get("/api/v1/key-rotation", headers=_h(editor)).status_code == 403

    # token emitido antes do kid existir
    with Session(get_engine()) as session:
        session.add(
            IntegrationToken(
                name="legado",
                jti="legado",
                created_by="owner",
                expires_at=datetime.now(UTC) + timedelta(days=3),
            )
        )
        session.commit()

    _set(
        db_url,
        jwt=_NEW,
        fernet=_NEW_FERNET,
        previous_jwt=_OLD[1],
        previous_fernet=_OLD_FERNET,
    )
    with _client() as client:
        # o token velho segue valendo durante a troca
        suite = client.get(
            f"/api/v1/configs/{agent_id}/eval-runs",
            headers={"Authorization": f"Bearer {old_token}"},
        )
        assert suite.status_code == 200, suite.text
        status = _status(client)
        assert status["jwt"] == {
            "current_kid": key_id(_NEW[1]),
            "previous_kid": key_id(_OLD[1]),
            "tokens_on_previous": 1,
            "tokens_without_kid": 1,
        }
        assert status["secrets"]["previous_configured"] is True
        assert status["secrets"]["pending"]["mcp_server"] == 1
        assert status["done"] is False
        listed = client.get("/api/v1/integrations", headers=_h(owner)).json()
        assert {i["name"]: i["on_current_key"] for i in listed} == {
            "sistema": False,
            "legado": False,
        }

        for item in listed:
            client.delete(f"/api/v1/integrations/{item['id']}", headers=_h(owner))
        assert rotate_secrets() == 0
        status = _status(client)
        assert status["jwt"]["tokens_on_previous"] == 0
        assert status["jwt"]["tokens_without_kid"] == 0
        assert set(status["secrets"]["pending"].values()) == {0}
        assert status["done"] is True
