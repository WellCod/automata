"""Destino de aviso por e-mail (ADR-0037)."""

import os
import ssl
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


class FakeSMTP:
    sent: list[Any] = []
    fail = False

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host, self.port = host, port
        self.tls = False
        self.user: str | None = None

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def starttls(self, context: Any = None) -> None:
        # sem contexto, o smtplib não confere o certificado (Fase 43)
        assert context is not None and context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        self.tls = True

    def login(self, user: str, password: str) -> None:
        self.user = user

    def send_message(self, message: Any) -> None:
        if FakeSMTP.fail:
            raise ConnectionRefusedError("smtp.empresa.com recusou para senha=xyz")
        FakeSMTP.sent.append((self, message))


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        os.environ["DATABASE_URL"] = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=False, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    import app.mailer as mailer

    FakeSMTP.sent = []
    FakeSMTP.fail = False
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.empresa.com")
    monkeypatch.setenv("SMTP_USER", "avisos@empresa.com")
    monkeypatch.setenv("SMTP_PASSWORD", "xyz")
    return FakeSMTP


EMAIL = {
    "name": "financeiro",
    "kind": "email",
    "emails": ["Ana@Empresa.com", "ana@empresa.com", "bia@empresa.com"],
    "events": ["budget.exceeded", "job.failed"],
}


def test_sem_smtp_o_tipo_nao_existe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert client.get("/api/v1/alert-destinations/channels").json() == {
        "webhook": True,
        "email": False,
    }
    assert client.post("/api/v1/alert-destinations", json=EMAIL).status_code == 422


def test_email_cadastra_avisa_e_testa(client: TestClient, smtp: type[FakeSMTP]) -> None:
    from app.alerts import broadcast
    from app.db import get_engine

    assert client.get("/api/v1/alert-destinations/channels").json()["email"] is True
    created = client.post("/api/v1/alert-destinations", json=EMAIL)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["kind"] == "email" and body["secret"] == ""
    assert body["emails"] == ["ana@empresa.com", "bia@empresa.com"]

    with Session(get_engine()) as session:
        delivered = broadcast(session, "job.failed", {"job_id": "j1"}, "Run de cobrança falhou.")
    assert delivered == 1
    conn, message = smtp.sent[-1]
    assert conn.tls is True and conn.user == "avisos@empresa.com"
    assert message["Subject"] == "[Automata] job.failed"
    assert message["To"] == "ana@empresa.com, bia@empresa.com"
    assert "Run de cobrança falhou." in message.get_content()

    tested = client.post(f"/api/v1/alert-destinations/{body['id']}/test").json()
    assert tested == {"status": "SMTP enviado", "delivered": True}

    smtp.fail = True
    failed = client.post(f"/api/v1/alert-destinations/{body['id']}/test").json()
    # o erro do servidor pode trazer credencial: só o tipo do erro sai
    assert failed == {"status": "falhou: ConnectionRefusedError", "delivered": False}


def test_validacao_por_tipo(client: TestClient, smtp: type[FakeSMTP]) -> None:
    sem_url = {"name": "x", "events": ["job.failed"]}
    assert client.post("/api/v1/alert-destinations", json=sem_url).status_code == 422
    sem_email = {**EMAIL, "emails": []}
    assert client.post("/api/v1/alert-destinations", json=sem_email).status_code == 422
    muitos = {**EMAIL, "emails": [f"p{i}@empresa.com" for i in range(6)]}
    assert client.post("/api/v1/alert-destinations", json=muitos).status_code == 422
    invalido = {**EMAIL, "emails": ["nao-e-email"]}
    assert client.post("/api/v1/alert-destinations", json=invalido).status_code == 422
