"""Gestão de usuários: só owner, sessões cortadas na hora e ao menos um owner ativo."""

import os
import time
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

_SENHA = "Senha12345678"


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


def _login(client: TestClient, email: str, senha: str = _SENHA) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": senha})
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


@pytest.fixture(scope="module")
def owner(client: TestClient) -> str:
    from app.auth import issue_token

    client.post(
        "/api/v1/auth/users",
        json={"email": "dono@example.com", "password": _SENHA, "role": "owner"},
        headers=_bearer(issue_token("bootstrap", ["agent_os:admin"])),
    ).raise_for_status()
    return _login(client, "dono@example.com")


def _criar(client: TestClient, owner: str, email: str, role: str = "editor") -> str:
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "password": _SENHA, "role": role},
        headers=_bearer(owner),
    )
    assert resp.status_code == 201, resp.text
    user_id: str = resp.json()["id"]
    return user_id


def test_me_e_lista_so_para_owner(client: TestClient, owner: str) -> None:
    me = client.get("/api/v1/me", headers=_bearer(owner)).json()
    assert me["email"] == "dono@example.com"
    assert me["role"] == "owner"

    _criar(client, owner, "editor@example.com")
    editor = _login(client, "editor@example.com")
    assert client.get("/api/v1/me", headers=_bearer(editor)).json()["role"] == "editor"
    assert client.get("/api/v1/users", headers=_bearer(editor)).status_code == 403

    users = client.get("/api/v1/users", headers=_bearer(owner)).json()
    emails = {u["email"]: u for u in users}
    assert {"dono@example.com", "editor@example.com"} <= set(emails)
    assert emails["editor@example.com"]["last_login_at"] is not None


def test_mudar_papel_derruba_sessao_aberta(client: TestClient, owner: str) -> None:
    user_id = _criar(client, owner, "papel@example.com")
    sessao = _login(client, "papel@example.com")
    assert client.get("/api/v1/configs", headers=_bearer(sessao)).status_code == 200

    resp = client.patch(f"/api/v1/users/{user_id}", json={"role": "viewer"}, headers=_bearer(owner))
    assert resp.json()["role"] == "viewer"
    assert client.get("/api/v1/configs", headers=_bearer(sessao)).status_code == 401

    time.sleep(1.1)  # o corte vale até o fim do segundo da mudança
    nova = _login(client, "papel@example.com")
    assert client.get("/api/v1/me", headers=_bearer(nova)).json()["role"] == "viewer"


def test_desativar_bloqueia_login_e_sessao(client: TestClient, owner: str) -> None:
    user_id = _criar(client, owner, "inativo@example.com")
    sessao = _login(client, "inativo@example.com")

    client.patch(
        f"/api/v1/users/{user_id}", json={"is_active": False}, headers=_bearer(owner)
    ).raise_for_status()
    assert client.get("/api/v1/me", headers=_bearer(sessao)).status_code == 401
    login = client.post(
        "/api/v1/auth/login", json={"email": "inativo@example.com", "password": _SENHA}
    )
    assert login.status_code == 401

    client.patch(
        f"/api/v1/users/{user_id}", json={"is_active": True}, headers=_bearer(owner)
    ).raise_for_status()
    time.sleep(1.1)
    _login(client, "inativo@example.com")


def test_redefinir_senha(client: TestClient, owner: str) -> None:
    user_id = _criar(client, owner, "senha@example.com")
    sessao = _login(client, "senha@example.com")

    fraca = client.post(
        f"/api/v1/users/{user_id}/password", json={"password": "curta"}, headers=_bearer(owner)
    )
    assert fraca.status_code == 422
    client.post(
        f"/api/v1/users/{user_id}/password",
        json={"password": "NovaSenha12345"},
        headers=_bearer(owner),
    ).raise_for_status()

    assert client.get("/api/v1/me", headers=_bearer(sessao)).status_code == 401
    time.sleep(1.1)
    _login(client, "senha@example.com", "NovaSenha12345")


def test_ultimo_owner_e_remocao(client: TestClient, owner: str) -> None:
    me = client.get("/api/v1/me", headers=_bearer(owner)).json()
    rebaixar = client.patch(
        f"/api/v1/users/{me['id']}", json={"role": "editor"}, headers=_bearer(owner)
    )
    assert rebaixar.status_code == 409
    assert "owner ativo" in rebaixar.text
    assert client.delete(f"/api/v1/users/{me['id']}", headers=_bearer(owner)).status_code == 409

    user_id = _criar(client, owner, "remover@example.com")
    ativo = client.delete(f"/api/v1/users/{user_id}", headers=_bearer(owner))
    assert ativo.status_code == 409
    assert "Desative" in ativo.text
    client.patch(
        f"/api/v1/users/{user_id}", json={"is_active": False}, headers=_bearer(owner)
    ).raise_for_status()
    assert client.delete(f"/api/v1/users/{user_id}", headers=_bearer(owner)).status_code == 204
    assert (
        client.patch(
            f"/api/v1/users/{user_id}", json={"is_active": True}, headers=_bearer(owner)
        ).status_code
        == 404
    )
