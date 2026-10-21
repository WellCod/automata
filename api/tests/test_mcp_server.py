"""Servidor MCP do AgentOS de verdade: o lifespan montado sobe e o protocolo responde."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        env = {
            "DATABASE_URL": pg.get_connection_url().replace("psycopg2", "psycopg"),
            "JWT_PRIVATE_KEY": key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ).decode(),
            "JWT_PUBLIC_KEY": key.public_key()
            .public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )
            .decode(),
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=True)
        ) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _rpc(client: TestClient, method: str, params: dict[str, Any], **headers: str) -> Any:
    from app.auth import issue_token

    token = issue_token("owner", ["agent_os:admin"])
    return client.post(
        "/mcp",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
            **headers,
        },
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )


def test_initialize_com_token_responde(client: TestClient) -> None:
    # antes, o lifespan do AgentOS montado não rodava e o /mcp dava 500
    resp = _rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "teste", "version": "1"},
        },
    )
    assert resp.status_code == 200, resp.text
    assert '"protocolVersion"' in resp.text
    assert resp.headers.get("mcp-session-id")
