"""Logout revoga o token da sessão por jti; os outros tokens do usuário seguem válidos."""

import json
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


def _sem_troca_obrigatoria(email: str) -> None:
    """Conta criada pelo owner nasce com senha provisória (ADR-0045); a troca tem teste
    próprio em test_senha_do_usuario.py, aqui só atrapalharia."""
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.user import User

    with Session(get_engine()) as session:
        session.execute(
            update(User).where(User.email == email.lower()).values(must_change_password=False)
        )
        session.commit()


def _login(client: TestClient, email: str) -> str:
    _sem_troca_obrigatoria(email)
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


def test_token_sem_prefixo_bearer_tambem_e_revogado(client: TestClient, editor: str) -> None:
    sessao = _login(client, editor)
    # o middleware JWT do Agno aceita o token cru (SEC-01)
    assert client.get("/agents", headers={"Authorization": sessao}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers={"Authorization": sessao}).status_code == 204
    assert client.get("/agents", headers={"Authorization": sessao}).status_code == 401
    assert client.get("/agents", headers={"Authorization": f"bearer  {sessao}"}).status_code == 401


def test_websocket_de_workflows_fechado(client: TestClient) -> None:
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/workflows/ws"):
        pass


def test_versao_especifica_so_para_quem_edita_config(client: TestClient) -> None:
    from app.auth import issue_token

    owner = _bearer(issue_token("owner", ["agent_os:admin"]))
    config_id = client.post(
        "/api/v1/configs",
        json={"name": "versao fixa", "description": "x", "kind": "agent"},
        headers=owner,
    ).json()["id"]
    payload = {"model_id": "claude-haiku-4-5", "instructions": {"objective": "v1"}}
    body = {"name": "versao fixa", "description": "x", "payload": payload}
    draft = client.put(f"/api/v1/configs/{config_id}/draft", json=body, headers=owner)
    draft.raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish", headers=owner).raise_for_status()
    version_id = client.get(f"/api/v1/configs/{config_id}", headers=owner).json()[
        "current_version"
    ]["id"]
    data = {
        "message": "oi",
        "stream": "false",
        "factory_input": json.dumps({"version_id": version_id}),
    }

    so_run = _bearer(issue_token("integration:x", ["agents:run"]))
    resp = client.post(f"/agents/{config_id}/runs", data=data, headers=so_run)
    assert resp.status_code == 403
    sem_versao = {k: v for k, v in data.items() if k != "factory_input"}
    assert client.post(f"/agents/{config_id}/runs", data=sem_versao, headers=so_run).is_success

    editor = _bearer(issue_token("editor", ["agents:run", "configs:write"]))
    assert client.post(f"/agents/{config_id}/runs", data=data, headers=editor).is_success
