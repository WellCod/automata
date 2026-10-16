"""Cadastro de servidores MCP: SSRF, cifra dos headers, rotas e permissões (ADR-0010)."""

import os
import socket
from collections.abc import Generator
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
from app.db import get_engine
from app.mcp.egress import EgressDenied, check_url
from app.models.mcp_server import McpServer
from app.secrets import SecretsKeyMissing, decrypt_json, encrypt_json
from app.settings import get_settings

_KEY = Fernet.generate_key().decode()


def _fake_dns(ip: str) -> Any:
    def resolve(host: str, *args: Any, **kwargs: Any) -> list[Any]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    return resolve


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql+psycopg://x"))
    monkeypatch.setenv("JWT_PRIVATE_KEY", os.environ.get("JWT_PRIVATE_KEY", "x"))
    monkeypatch.setenv("JWT_PUBLIC_KEY", os.environ.get("JWT_PUBLIC_KEY", "x"))
    monkeypatch.setenv("MCP_SECRETS_KEY", _KEY)
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.interno.local")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- egress ---


@pytest.mark.parametrize("ip", ["10.0.0.5", "127.0.0.1", "169.254.169.254", "192.168.1.1"])
def test_recusa_host_que_resolve_para_rede_interna(
    env: None, monkeypatch: pytest.MonkeyPatch, ip: str
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns(ip))
    with pytest.raises(EgressDenied):
        check_url("https://mcp.exemplo.com/mcp")


def test_aceita_host_publico(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("93.184.216.34"))
    check_url("https://mcp.exemplo.com/mcp")


def test_http_so_para_host_liberado(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("93.184.216.34"))
    with pytest.raises(EgressDenied):
        check_url("http://mcp.exemplo.com/mcp")
    check_url("http://mcp.interno.local:8080/mcp")


def test_esquema_invalido(env: None) -> None:
    with pytest.raises(EgressDenied):
        check_url("file:///etc/passwd")


# --- segredos ---


def test_segredo_ida_e_volta(env: None) -> None:
    token = encrypt_json({"Authorization": "Bearer abc"})
    assert "abc" not in token
    assert decrypt_json(token) == {"Authorization": "Bearer abc"}


def test_sem_chave_recusa(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_SECRETS_KEY")
    get_settings.cache_clear()
    with pytest.raises(SecretsKeyMissing):
        encrypt_json({"a": "b"})


def test_chave_errada_recusa(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    token = encrypt_json({"a": "b"})
    monkeypatch.setenv("MCP_SECRETS_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with pytest.raises(SecretsKeyMissing):
        decrypt_json(token)


# --- rotas com Postgres ---


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
def client(db_url: str, env: None) -> Generator[TestClient, None, None]:
    from app.main import create_app

    with TestClient(create_app(auto_provision_dbs=False, enable_auth=False)) as c:
        yield c


_BODY = {
    "name": "CRM",
    "slug": "crm",
    "url": "http://mcp.interno.local:8080/mcp",
    "headers": {"Authorization": "Bearer segredo-do-crm"},
}


def test_crud_nao_devolve_segredo(client: TestClient) -> None:
    created = client.post("/api/v1/mcp-servers", json=_BODY)
    assert created.status_code == 201, created.text
    data = created.json()
    assert data["header_names"] == ["Authorization"]
    assert "segredo-do-crm" not in created.text

    with Session(get_engine()) as session:
        row = session.get(McpServer, data["id"])
        assert row is not None
        assert row.headers_encrypted is not None
        assert "segredo-do-crm" not in row.headers_encrypted
        assert decrypt_json(row.headers_encrypted)["Authorization"] == "Bearer segredo-do-crm"

    # headers ausentes mantêm o segredo; {} apaga
    kept = client.put(f"/api/v1/mcp-servers/{data['id']}", json={**_BODY, "headers": None})
    assert kept.json()["header_names"] == ["Authorization"]
    cleared = client.put(f"/api/v1/mcp-servers/{data['id']}", json={**_BODY, "headers": {}})
    assert cleared.json()["header_names"] == []

    assert client.post("/api/v1/mcp-servers", json=_BODY).status_code == 409
    assert client.delete(f"/api/v1/mcp-servers/{data['id']}").status_code == 204
    assert client.get(f"/api/v1/mcp-servers/{data['id']}").status_code == 404


def test_url_interna_recusada_na_escrita(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", _fake_dns("169.254.169.254"))
    body = {**_BODY, "slug": "meta", "name": "meta", "url": "https://metadata.exemplo.com/"}
    resp = client.post("/api/v1/mcp-servers", json=body)
    assert resp.status_code == 422
    assert "interno" in resp.text


def test_trocar_url_descarta_tools_descobertas(client: TestClient) -> None:
    created = client.post("/api/v1/mcp-servers", json={**_BODY, "slug": "erp", "name": "ERP"})
    server_id = created.json()["id"]
    with Session(get_engine()) as session:
        row = session.get(McpServer, server_id)
        assert row is not None
        row.tools_snapshot = [{"name": "buscar", "description": None, "input_schema": {}}]
        session.commit()

    same = client.put(
        f"/api/v1/mcp-servers/{server_id}", json={**_BODY, "slug": "erp", "name": "ERP"}
    )
    assert same.json()["tools"] is not None
    moved = client.put(
        f"/api/v1/mcp-servers/{server_id}",
        json={**_BODY, "slug": "erp", "name": "ERP", "url": "http://mcp.interno.local:9090/mcp"},
    )
    assert moved.json()["tools"] is None


def test_slug_invalido(client: TestClient) -> None:
    resp = client.post("/api/v1/mcp-servers", json={**_BODY, "slug": "Com Espaco"})
    assert resp.status_code == 422


# --- permissões ---


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


@pytest.mark.parametrize(("role", "esperado_escrita"), [("viewer", 403), ("editor", 403)])
def test_so_owner_cadastra_servidor(
    monkeypatch: pytest.MonkeyPatch, role: str, esperado_escrita: int
) -> None:
    from app.auth import issue_token
    from app.main import create_app
    from app.models.user import UserRole
    from app.schemas.user import ROLE_SCOPES

    priv, pub = _keys()
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", priv)
    monkeypatch.setenv("JWT_PUBLIC_KEY", pub)
    get_settings.cache_clear()
    client = TestClient(
        create_app(auto_provision_dbs=False, enable_auth=True), raise_server_exceptions=False
    )
    headers = {"Authorization": f"Bearer {issue_token(role, ROLE_SCOPES[UserRole(role)])}"}

    assert client.post("/api/v1/mcp-servers", json=_BODY, headers=headers).status_code == 403
    # leitura passa da autorização (falha depois, sem banco)
    assert client.get("/api/v1/mcp-servers", headers=headers).status_code not in (401, 403)

    admin = {"Authorization": f"Bearer {issue_token('owner', ['agent_os:admin'])}"}
    resp = client.post("/api/v1/mcp-servers", json=_BODY, headers=admin)
    assert resp.status_code not in (401, 403)
    get_settings.cache_clear()


# --- descoberta contra servidor MCP real ---


@pytest.fixture(scope="module")
def mcp_url() -> Generator[str, None, None]:
    from tests.mcp_fake_server import running_server

    with running_server() as url:
        yield url


@pytest.fixture
def local_env(env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "127.0.0.1")
    get_settings.cache_clear()


def test_descoberta_lista_tools_e_salva_retrato(
    client: TestClient, mcp_url: str, local_env: None
) -> None:
    from tests.mcp_fake_server import TOKEN

    body = {
        "name": "CRM real",
        "slug": "crmreal",
        "url": mcp_url,
        "headers": {"Authorization": f"Bearer {TOKEN}"},
    }
    server_id = client.post("/api/v1/mcp-servers", json=body).json()["id"]

    resp = client.post(f"/api/v1/mcp-servers/{server_id}/discover")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    names = sorted(t["name"] for t in data["tools"])
    assert names == ["buscar_cliente", "cancelar_assinatura"]
    assert data["tools_discovered_at"] is not None
    buscar = next(t for t in data["tools"] if t["name"] == "buscar_cliente")
    assert "cliente_id" in buscar["input_schema"]["properties"]


def test_descoberta_sem_token_falha_com_502(
    client: TestClient, mcp_url: str, local_env: None
) -> None:
    body = {"name": "CRM sem token", "slug": "crmsemtoken", "url": mcp_url}
    server_id = client.post("/api/v1/mcp-servers", json=body).json()["id"]

    resp = client.post(f"/api/v1/mcp-servers/{server_id}/discover")
    assert resp.status_code == 502
    assert "crmsemtoken" in resp.json()["detail"]


def test_descoberta_servidor_fora_do_ar_falha_com_502(client: TestClient, local_env: None) -> None:
    body = {"name": "Fora do ar", "slug": "foradoar", "url": "http://127.0.0.1:1/mcp"}
    server_id = client.post("/api/v1/mcp-servers", json=body).json()["id"]

    resp = client.post(f"/api/v1/mcp-servers/{server_id}/discover")
    assert resp.status_code == 502
    # a API segue respondendo depois da falha
    assert client.get(f"/api/v1/mcp-servers/{server_id}").status_code == 200
