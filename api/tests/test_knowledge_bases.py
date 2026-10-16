"""Cadastro de bases de conhecimento: rotas, embedder fixo, tabela de vetores e papéis."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.settings import get_settings


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from app.main import create_app

    monkeypatch.setenv("VOYAGE_API_KEY", "pa-teste")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEMO_REPLAY", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app(auto_provision_dbs=False, enable_auth=False)) as c:
        yield c
    get_settings.cache_clear()


_BODY = {"name": "Políticas de RH", "slug": "rh", "description": "Férias, benefícios e reembolso"}


def test_crud_com_embedder_padrao(client: TestClient) -> None:
    created = client.post("/api/v1/knowledge-bases", json=_BODY)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["embedder"] == "voyage"
    assert data["embedder_model"] == "voyage-3.5"
    assert data["dimensions"] == 1024
    assert data["chunk_size"] == 2000
    assert "vector_table" not in data

    assert client.post("/api/v1/knowledge-bases", json=_BODY).status_code == 409
    assert client.get("/api/v1/knowledge-bases").json()[0]["slug"] == "rh"

    updated = client.put(
        f"/api/v1/knowledge-bases/{data['id']}",
        json={"name": "RH", "description": "Só políticas internas", "chunk_size": 1000},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "RH"
    assert updated.json()["slug"] == "rh"
    assert updated.json()["embedder"] == "voyage"

    assert client.delete(f"/api/v1/knowledge-bases/{data['id']}").status_code == 204
    assert client.get(f"/api/v1/knowledge-bases/{data['id']}").status_code == 404


def test_embedder_sem_chave_recusado(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={**_BODY, "name": "Docs", "slug": "docs", "embedder": "openai"},
    )
    assert resp.status_code == 422
    assert "OPENAI_API_KEY" in resp.text


def test_demo_replay_libera_embedder_sem_chave(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_REPLAY", "true")
    resp = client.post(
        "/api/v1/knowledge-bases",
        json={**_BODY, "name": "Demo", "slug": "demo", "embedder": "openai"},
    )
    assert resp.status_code == 201, resp.text
    client.delete(f"/api/v1/knowledge-bases/{resp.json()['id']}")


def test_lista_embedders_com_estado_da_chave(client: TestClient) -> None:
    infos = {e["name"]: e for e in client.get("/api/v1/knowledge-bases/embedders").json()}
    assert infos["voyage"]["configured"] is True
    assert infos["voyage"]["default"] is True
    assert infos["openai"]["configured"] is False


def test_remover_base_apaga_tabela_de_vetores(client: TestClient) -> None:
    created = client.post(
        "/api/v1/knowledge-bases", json={**_BODY, "name": "Manuais", "slug": "manuais"}
    ).json()
    table = f"kb_{created['id'].replace('-', '')}"
    with Session(get_engine()) as session:
        session.execute(text("CREATE SCHEMA IF NOT EXISTS ai"))
        session.execute(text(f'CREATE TABLE ai."{table}" (id int)'))
        session.commit()

    assert client.delete(f"/api/v1/knowledge-bases/{created['id']}").status_code == 204

    with Session(get_engine()) as session:
        exists = session.execute(text("SELECT to_regclass(:t)"), {"t": f"ai.{table}"}).scalar()
    assert exists is None


def test_slug_invalido(client: TestClient) -> None:
    resp = client.post("/api/v1/knowledge-bases", json={**_BODY, "slug": "Com Espaco"})
    assert resp.status_code == 422


# --- papéis ---


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


@pytest.mark.parametrize(("role", "pode_escrever"), [("viewer", False), ("editor", True)])
def test_viewer_le_e_editor_escreve(
    monkeypatch: pytest.MonkeyPatch, role: str, pode_escrever: bool
) -> None:
    from app.auth import issue_token
    from app.main import create_app
    from app.models.user import UserRole
    from app.schemas.user import ROLE_SCOPES

    priv, pub = _keys()
    # porta fechada com timeout curto: não depende do que roda na máquina
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/db?connect_timeout=1")
    monkeypatch.setenv("JWT_PRIVATE_KEY", priv)
    monkeypatch.setenv("JWT_PUBLIC_KEY", pub)
    get_settings.cache_clear()
    client = TestClient(
        create_app(auto_provision_dbs=False, enable_auth=True), raise_server_exceptions=False
    )
    headers = {"Authorization": f"Bearer {issue_token(role, ROLE_SCOPES[UserRole(role)])}"}

    # sem banco a rota falha depois da autorização: só interessa não ser 401/403
    assert client.get("/api/v1/knowledge-bases", headers=headers).status_code not in (401, 403)
    write = client.post("/api/v1/knowledge-bases", json=_BODY, headers=headers).status_code
    assert (write not in (401, 403)) is pode_escrever
    get_settings.cache_clear()
