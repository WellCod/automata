"""Ver, apagar e vencer memórias (ADR-0025), com os papéis de verdade."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from agno.db.schemas.memory import UserMemory
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.models.user import UserRole
from app.schemas.user import ROLE_SCOPES
from app.settings import get_settings


def _keys() -> tuple[str, str]:
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
    private, public = _keys()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {"DATABASE_URL": url, "JWT_PRIVATE_KEY": private, "JWT_PUBLIC_KEY": public}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
        ) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _auth(sub: str, scopes: list[str]) -> dict[str, str]:
    from app.auth import issue_token

    return {"Authorization": f"Bearer {issue_token(sub, scopes)}"}


OWNER = ("owner-1", ["agent_os:admin"])


def _agent(client: TestClient, name: str, retention: int = 90) -> str:
    h = _auth(*OWNER)
    body = {"name": name, "description": "x"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": "agent"}, headers=h).json()[
        "id"
    ]
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={
            **body,
            "payload": {
                "model_id": "claude-haiku-4-5",
                "memory": {"enabled": True, "retention_days": retention},
            },
        },
        headers=h,
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish", headers=h).raise_for_status()
    return str(config_id)


def _remember(agent: str, user: str, text: str, age_days: int = 0) -> str:
    from app.agents.memory import memory_db

    memory_id = str(uuid4())
    memory_db().upsert_user_memory(
        UserMemory(memory_id=memory_id, user_id=user, agent_id=agent, memory=text)
    )
    if age_days:
        # updated_at é epoch em segundos; envelhece direto na tabela do Agno
        from sqlalchemy import text as sql

        from app.db import get_engine

        old = int((datetime.now(UTC) - timedelta(days=age_days)).timestamp())
        with get_engine().begin() as conn:
            conn.execute(
                sql(
                    "UPDATE ai.agno_memories SET updated_at = :t, created_at = :t "
                    "WHERE memory_id = :m"
                ),
                {"t": old, "m": memory_id},
            )
    return memory_id


def test_owner_ve_e_apaga_por_agente_e_editor_nao(client: TestClient) -> None:
    agent = _agent(client, "loja memória")
    _remember(agent, "cliente-1", "Prefere entrega à tarde")
    _remember(agent, "cliente-2", "Mora em Curitiba")
    base = f"/api/v1/configs/{agent}/memories"

    owner = _auth(*OWNER)
    listed = client.get(base, headers=owner).json()
    assert {m["user_id"] for m in listed} == {"cliente-1", "cliente-2"}
    only = client.get(base, params={"user_id": "cliente-1"}, headers=owner).json()
    assert [m["memory"] for m in only] == ["Prefere entrega à tarde"]

    # editor configura agente, mas não lê dado pessoal de usuário final
    editor = _auth("editor-1", ROLE_SCOPES[UserRole.editor])
    assert client.get(base, headers=editor).status_code == 403

    assert client.delete(base, params={"user_id": "cliente-1"}, headers=owner).status_code == 204
    left = client.get(base, headers=owner).json()
    assert [m["user_id"] for m in left] == ["cliente-2"]
    assert client.delete(f"{base}/{left[0]['memory_id']}", headers=owner).status_code == 204
    assert client.get(base, headers=owner).json() == []


def test_usuario_ve_e_apaga_so_as_proprias(client: TestClient) -> None:
    loja = _agent(client, "loja eu")
    cobranca = _agent(client, "cobrança eu")
    mine = _remember(loja, "ana", "Veste M")
    _remember(cobranca, "ana", "Paga no dia 10")
    other = _remember(loja, "bruno", "Veste G")

    ana = _auth("ana", ROLE_SCOPES[UserRole.viewer])
    listed = client.get("/api/v1/me/memories", headers=ana).json()
    assert sorted((m["agent_name"], m["memory"]) for m in listed) == [
        ("cobrança eu", "Paga no dia 10"),
        ("loja eu", "Veste M"),
    ]
    # memória de outra pessoa: como se não existisse
    assert client.delete(f"/api/v1/me/memories/{other}", headers=ana).status_code == 404
    assert client.delete(f"/api/v1/me/memories/{mine}", headers=ana).status_code == 204
    assert client.delete("/api/v1/me/memories", headers=ana).status_code == 204
    assert client.get("/api/v1/me/memories", headers=ana).json() == []
    bruno = _auth("bruno", ROLE_SCOPES[UserRole.viewer])
    assert [m["memory"] for m in client.get("/api/v1/me/memories", headers=bruno).json()] == [
        "Veste G"
    ]


def test_retencao_apaga_o_que_venceu(client: TestClient) -> None:
    from app.agents import memory_admin

    curta = _agent(client, "retenção curta", retention=7)
    longa = _agent(client, "retenção longa", retention=365)
    velha = _remember(curta, "carla", "Fato antigo", age_days=30)
    nova = _remember(curta, "carla", "Fato recente")
    guardada = _remember(longa, "carla", "Fato antigo, mas a retenção é longa", age_days=30)

    assert memory_admin.purge_expired() >= 1
    ids = {m.memory_id for m in memory_admin.memories(user_id="carla")}
    assert velha not in ids
    assert {nova, guardada} <= ids
