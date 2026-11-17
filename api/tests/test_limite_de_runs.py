"""Limite de runs por quem chama e orçamento padrão do token de integração (LLM-05)."""

from collections.abc import Generator

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
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    pub = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        patch = pytest.MonkeyPatch()
        for k, v in {
            "DATABASE_URL": pg.get_connection_url().replace("psycopg2", "psycopg"),
            "JWT_PRIVATE_KEY": priv,
            "JWT_PUBLIC_KEY": pub,
            "DEMO_REPLAY": "true",
            "RUN_RATE_LIMIT_PER_MINUTE": "3",
            "DEFAULT_INTEGRATION_BUDGET_USD": "25",
        }.items():
            patch.setenv(k, v)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
        ) as c:
            yield c
        patch.undo()
        get_settings.cache_clear()


def _owner() -> dict[str, str]:
    from app.auth import issue_token

    return {"Authorization": f"Bearer {issue_token('owner', ['agent_os:admin'])}"}


def _agent(client: TestClient) -> str:
    owner = _owner()
    agent_id = str(
        client.post(
            "/api/v1/configs", json={"name": "limite", "description": "x"}, headers=owner
        ).json()["id"]
    )
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={"name": "limite", "description": "x", "payload": {"model_id": "claude-haiku-4-5"}},
        headers=owner,
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish", headers=owner).raise_for_status()
    return agent_id


def test_token_de_integracao_nasce_com_orcamento_e_passa_do_limite_por_minuto(
    client: TestClient,
) -> None:
    agent_id = _agent(client)
    issued = client.post(
        "/api/v1/integrations",
        json={"name": "site", "agent_ids": [agent_id], "expires_in_days": 30},
        headers=_owner(),
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]
    subject = f"integration:{issued.json()['id']}"

    budgets = client.get("/api/v1/caller-budgets", headers=_owner()).json()
    mine = next(b for b in budgets if b["subject"] == subject)
    assert float(mine["monthly_usd"]) == 25 and mine["hard_stop"] is True

    headers = {"Authorization": f"Bearer {token}"}
    data = {"message": "oi", "stream": "false"}
    codes = [
        client.post(f"/agents/{agent_id}/runs", data=data, headers=headers).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
    # o limite é de quem chama: outro chamador segue
    assert client.post(f"/agents/{agent_id}/runs", data=data, headers=_owner()).status_code == 200
