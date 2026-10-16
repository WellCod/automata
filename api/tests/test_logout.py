"""Logout revoga o token da sessão por jti; os outros tokens do usuário seguem válidos."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import jwt
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
    with PostgresContainer("postgres:17") as pg:
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


def _login(client: TestClient, email: str) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": "Senha12345678"})
    assert resp.status_code == 200
    token: str = resp.json()["access_token"]
    return token


@pytest.fixture(scope="module")
def editor(client: TestClient) -> str:
    from app.auth import issue_token

    email = "logout@example.com"
    resp = client.post(
        "/api/v1/auth/users",
        json={"email": email, "password": "Senha12345678", "role": "editor"},
        headers=_bearer(issue_token("owner", ["agent_os:admin"])),
    )
    assert resp.status_code == 201
    return email


def test_logout_revoga_so_o_token_da_sessao(client: TestClient, editor: str) -> None:
    sessao = _login(client, editor)
    outra = _login(client, editor)
    claims = jwt.decode(sessao, options={"verify_signature": False})
    assert claims["jti"] != jwt.decode(outra, options={"verify_signature": False})["jti"]
    assert client.get("/api/v1/configs", headers=_bearer(sessao)).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=_bearer(sessao)).status_code == 204

    assert client.get("/api/v1/configs", headers=_bearer(sessao)).status_code == 401
    assert client.get("/agents", headers=_bearer(sessao)).status_code == 401
    assert client.get("/api/v1/configs", headers=_bearer(outra)).status_code == 200

    # vale também depois de recarregar a lista do banco (outra réplica, restart)
    from app.integrations import RevokedTokens

    assert RevokedTokens().is_revoked(claims["jti"])


def test_logout_repetido_e_token_sem_jti(client: TestClient) -> None:
    from app.auth import issue_token
    from app.settings import get_settings

    sem_jti = jwt.encode(
        {"sub": "antigo", "scopes": ["configs:read"], "aud": "automata", "exp": 4102444800},
        get_settings().jwt_private_key,
        algorithm="RS256",
    )
    assert client.post("/api/v1/auth/logout", headers=_bearer(sem_jti)).status_code == 204
    assert client.get("/api/v1/configs", headers=_bearer(sem_jti)).status_code == 200

    token = issue_token("u", ["configs:read"])
    assert client.post("/api/v1/auth/logout", headers=_bearer(token)).status_code == 204
    # já revogado: o middleware recusa antes de chegar à rota
    assert client.post("/api/v1/auth/logout", headers=_bearer(token)).status_code == 401


def test_logout_com_token_invalido(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=_bearer("lixo")).status_code == 401


def test_revogado_expirado_sai_da_lista(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.integrations import _load_revoked
    from app.models.revoked_token import RevokedToken

    with Session(get_engine()) as session:
        session.add(
            RevokedToken(
                jti="expirado",
                user_id="u",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        session.commit()
    assert "expirado" not in _load_revoked()
