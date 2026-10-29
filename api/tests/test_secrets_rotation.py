"""Rotação da chave dos segredos (ADR-0026): chave anterior só decifra e o comando recifra."""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

_OLD = Fernet.generate_key().decode()
_NEW = Fernet.generate_key().decode()


def _keys(monkeypatch: pytest.MonkeyPatch, current: str, previous: str | None = None) -> None:
    monkeypatch.setenv("MCP_SECRETS_KEY", current)
    if previous:
        monkeypatch.setenv("MCP_SECRETS_PREVIOUS_KEY", previous)
    else:
        monkeypatch.delenv("MCP_SECRETS_PREVIOUS_KEY", raising=False)
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", os.environ.get("DATABASE_URL", "postgresql://x"))
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    yield
    get_settings.cache_clear()


def test_chave_anterior_so_decifra(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.secrets import SecretsKeyMissing, decrypt_json, encrypt_json, on_current_key

    _keys(monkeypatch, _OLD)
    old_token = encrypt_json({"token": "ghp_x"})

    _keys(monkeypatch, _NEW)
    with pytest.raises(SecretsKeyMissing):
        decrypt_json(old_token)

    _keys(monkeypatch, _NEW, previous=_OLD)
    assert decrypt_json(old_token) == {"token": "ghp_x"}
    assert not on_current_key(old_token)
    new_token = encrypt_json({"token": "ghp_y"})
    assert on_current_key(new_token)


def test_reencrypt_passa_para_a_atual_e_recusa_chave_desconhecida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.secrets import SecretsKeyMissing, decrypt_json, encrypt_json, on_current_key, reencrypt

    _keys(monkeypatch, _OLD)
    old_token = encrypt_json({"a": "1"})
    _keys(monkeypatch, _NEW, previous=_OLD)
    rotated = reencrypt(old_token)
    assert on_current_key(rotated)
    _keys(monkeypatch, _NEW)
    assert decrypt_json(rotated) == {"a": "1"}

    _keys(monkeypatch, Fernet.generate_key().decode())
    with pytest.raises(SecretsKeyMissing):
        reencrypt(rotated)


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def test_comando_recifra_tudo_e_e_idempotente(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.db import get_engine
    from app.models.alert import AlertDestination
    from app.models.mcp_server import McpServer
    from app.rotate_secrets import RotationError, pending, rotate_all
    from app.secrets import decrypt_json, encrypt_json

    monkeypatch.setenv("DATABASE_URL", db_url)
    _keys(monkeypatch, _OLD)
    with Session(get_engine()) as session:
        session.add(
            McpServer(
                name="crm",
                slug="crm",
                url="https://crm.example.com/mcp",
                headers_encrypted=encrypt_json({"Authorization": "Bearer x"}),
                updated_by="owner",
            )
        )
        session.add(
            AlertDestination(
                name="#ops",
                webhook_encrypted=encrypt_json({"url": "https://h.example.com/a", "secret": "z"}),
                webhook_host="hooks.example.com",
                created_by="owner",
            )
        )
        session.commit()

    _keys(monkeypatch, _NEW, previous=_OLD)
    with Session(get_engine()) as session:
        assert pending(session)["mcp_server"] == 1
        assert pending(session)["alert_destination"] == 1
        changed = rotate_all(session)
        session.commit()
    assert changed == {
        "mcp_server": 1,
        "eval_schedule": 0,
        "alert_destination": 1,
        "knowledge_connector": 0,
    }

    # sem a anterior, tudo abre só com a atual
    _keys(monkeypatch, _NEW)
    with Session(get_engine()) as session:
        assert set(pending(session).values()) == {0}
        assert rotate_all(session) == dict.fromkeys(changed, 0)
        server = session.scalars(select(McpServer)).one()
        assert decrypt_json(server.headers_encrypted or "") == {"Authorization": "Bearer x"}

        # valor que nenhuma chave abre interrompe sem gravar o resto
        session.add(
            McpServer(
                name="estranho",
                slug="estranho",
                url="https://x.example.com/mcp",
                headers_encrypted=Fernet(Fernet.generate_key()).encrypt(b"{}").decode(),
                updated_by="owner",
            )
        )
        session.commit()
    _keys(monkeypatch, Fernet.generate_key().decode(), previous=_NEW)
    with Session(get_engine()) as session, pytest.raises(RotationError, match="mcp_server"):
        rotate_all(session)
