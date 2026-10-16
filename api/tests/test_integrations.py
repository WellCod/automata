"""Tokens de integração: acesso só aos recursos liberados e revogação imediata (ADR-0009)."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


def _keys() -> tuple[str, str]:
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
    return priv, pub


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    priv, pub = _keys()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": priv,
            "JWT_PUBLIC_KEY": pub,
            "DEMO_REPLAY": "true",
            "PUBLIC_BASE_URL": "https://api.exemplo.com",
        }
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


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _owner() -> dict[str, str]:
    from app.auth import issue_token

    return _bearer(issue_token("owner", ["agent_os:admin"]))


def _publish(client: TestClient, name: str) -> str:
    h = _owner()
    agent_id = client.post(
        "/api/v1/configs", json={"name": name, "description": f"Use para {name}"}, headers=h
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={"name": name, "description": f"Use para {name}", "payload": {"model_id": "gpt-4o"}},
        headers=h,
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish", headers=h).raise_for_status()
    return str(agent_id)


def test_token_ve_e_executa_so_o_liberado_e_revogacao_vale_na_hora(client: TestClient) -> None:
    liberado = _publish(client, "liberado")
    outro = _publish(client, "outro")

    resp = client.post(
        "/api/v1/integrations",
        json={"name": "crm externo", "agent_ids": [liberado], "expires_in_days": 7},
        headers=_owner(),
    )
    assert resp.status_code == 201, resp.text
    issued = resp.json()
    assert issued["mcp_url"] == "https://api.exemplo.com/mcp"
    h = _bearer(issued["token"])

    visiveis = [a["id"] for a in client.get("/agents", headers=h).json()]
    assert visiveis == [liberado]
    run = client.post(
        f"/agents/{liberado}/runs", data={"message": "oi", "stream": "false"}, headers=h
    )
    assert run.status_code == 200, run.text
    negado = client.post(
        f"/agents/{outro}/runs", data={"message": "oi", "stream": "false"}, headers=h
    )
    assert negado.status_code == 403
    # token de integração não mexe em config
    assert client.get("/api/v1/configs", headers=h).status_code == 403

    listed = client.get("/api/v1/integrations", headers=_owner()).json()
    assert "token" not in listed[0]

    client.delete(f"/api/v1/integrations/{issued['id']}", headers=_owner()).raise_for_status()
    assert client.get("/agents", headers=h).status_code == 401


def test_so_owner_emite_token(client: TestClient) -> None:
    from app.auth import issue_token
    from app.models.user import UserRole
    from app.schemas.user import ROLE_SCOPES

    agente = _publish(client, "para-editor")
    for role in (UserRole.editor, UserRole.viewer):
        h = _bearer(issue_token(role.value, ROLE_SCOPES[role]))
        resp = client.post(
            "/api/v1/integrations", json={"name": "x", "agent_ids": [agente]}, headers=h
        )
        assert resp.status_code == 403


def test_recusa_recurso_invalido(client: TestClient) -> None:
    import uuid

    h = _owner()
    nao_publicado = client.post(
        "/api/v1/configs", json={"name": "rascunho", "description": "x"}, headers=h
    ).json()["id"]
    for body in (
        {"name": "x"},
        {"name": "x", "agent_ids": [str(uuid.uuid4())]},
        {"name": "x", "agent_ids": [nao_publicado]},
        {"name": "x", "team_ids": [_publish(client, "agente-nao-e-time")]},
    ):
        assert client.post("/api/v1/integrations", json=body, headers=h).status_code == 400
    assert (
        client.post(
            "/api/v1/integrations",
            json={"name": "x", "agent_ids": [nao_publicado], "expires_in_days": 365},
            headers=h,
        ).status_code
        == 422
    )


def test_revogados_com_banco_fora_nao_consulta_a_cada_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.integrations as integrations

    chamadas = 0

    def boom() -> set[str]:
        nonlocal chamadas
        chamadas += 1
        raise RuntimeError("db fora")

    monkeypatch.setattr(integrations, "_load_revoked", boom)
    revoked = integrations.RevokedTokens(ttl_seconds=60)
    assert not revoked.is_revoked("a")
    assert not revoked.is_revoked("b")
    assert chamadas == 1
