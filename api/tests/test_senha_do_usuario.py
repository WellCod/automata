"""Senha do próprio usuário (ADR-0045, COM-04).

Antes só o owner criava e redefinia senha, e a pessoa nunca trocava a que ele escolheu:
o owner conhecia a senha de todo mundo indefinidamente, e não havia recuperação.
"""

import os
import re
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

SENHA_OWNER = "Provisoria123456"
SENHA_NOVA = "MinhaSenha98765"


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
def client() -> Generator[TestClient]:
    priv, pub = _keys()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        patch = pytest.MonkeyPatch()
        for k, v in {
            "DATABASE_URL": pg.get_connection_url().replace("psycopg2", "psycopg"),
            "JWT_PRIVATE_KEY": priv,
            "JWT_PUBLIC_KEY": pub,
            "DEMO_REPLAY": "true",
            "PUBLIC_URL": "https://painel.exemplo.com",
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


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _owner() -> dict[str, str]:
    from app.auth import issue_token

    return _bearer(issue_token("owner", ["agent_os:admin"]))


def _login(client: TestClient, email: str, password: str) -> dict[str, object]:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    body: dict[str, object] = resp.json()
    return body


def _new_user(client: TestClient, email: str) -> None:
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "password": SENHA_OWNER, "role": "editor"},
        headers=_owner(),
    )
    assert resp.status_code == 201, resp.text


def test_senha_do_owner_e_provisoria_e_a_pessoa_troca(client: TestClient) -> None:
    _new_user(client, "ana@empresa.com")
    first = _login(client, "ana@empresa.com", SENHA_OWNER)
    assert first["must_change_password"] is True
    limited = _bearer(str(first["access_token"]))
    # o token provisório não abre nada além de /me
    assert client.get("/api/v1/configs", headers=limited).status_code == 403
    assert client.get("/api/v1/me", headers=limited).status_code == 200

    wrong = {"current_password": "Errada1234567", "new_password": SENHA_NOVA}
    assert client.post("/api/v1/me/password", json=wrong, headers=limited).status_code == 400
    same = {"current_password": SENHA_OWNER, "new_password": SENHA_OWNER}
    assert client.post("/api/v1/me/password", json=same, headers=limited).status_code == 400

    ok = {"current_password": SENHA_OWNER, "new_password": SENHA_NOVA}
    resp = client.post("/api/v1/me/password", json=ok, headers=limited)
    assert resp.status_code == 200, resp.text
    full = _bearer(resp.json()["access_token"])
    assert client.get("/api/v1/configs", headers=full).status_code == 200

    # a senha que o owner conhecia não entra mais
    resp = client.post(
        "/api/v1/auth/login", json={"email": "ana@empresa.com", "password": SENHA_OWNER}
    )
    assert resp.status_code == 401
    assert _login(client, "ana@empresa.com", SENHA_NOVA)["must_change_password"] is False


def test_redefinir_pelo_owner_volta_a_exigir_troca(client: TestClient) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.user import User

    _new_user(client, "bia@empresa.com")
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.email == "bia@empresa.com"))
        assert user is not None
        user_id = user.id
    resp = client.post(
        f"/api/v1/users/{user_id}/password", json={"password": SENHA_NOVA}, headers=_owner()
    )
    assert resp.status_code == 200
    assert _login(client, "bia@empresa.com", SENHA_NOVA)["must_change_password"] is True


def test_recuperacao_por_email_com_link_de_uso_unico(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.mailer as mailer

    sent: list[tuple[list[str], str]] = []
    monkeypatch.setattr(mailer, "configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, text)) or "ok")
    _new_user(client, "caio@empresa.com")

    # e-mail que não existe responde igual e não manda nada
    resp = client.post("/api/v1/auth/password/forgot", json={"email": "ninguem@empresa.com"})
    assert resp.status_code == 202 and sent == []

    resp = client.post("/api/v1/auth/password/forgot", json={"email": "Caio@Empresa.com"})
    assert resp.status_code == 202
    [(to, text)] = sent
    assert to == ["caio@empresa.com"]
    match = re.search(r"https://painel\.exemplo\.com/redefinir-senha\?token=(\S+)", text)
    assert match
    token = match.group(1)

    body = {"token": token, "new_password": SENHA_NOVA}
    resp = client.post("/api/v1/auth/password/reset", json=body)
    assert resp.status_code == 200, resp.text
    assert client.get("/api/v1/configs", headers=_bearer(resp.json()["access_token"])).is_success
    assert client.post("/api/v1/auth/password/reset", json=body).status_code == 400
    assert _login(client, "caio@empresa.com", SENHA_NOVA)["must_change_password"] is False


def test_link_vencido_e_recusado(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.repositories.user import UserRepository
    from app.services.user import UserService

    _new_user(client, "dani@empresa.com")
    past = datetime.now(UTC) - timedelta(hours=1)
    with Session(get_engine()) as session:
        found = UserService(UserRepository(session)).request_reset("dani@empresa.com", past)
        session.commit()
    assert found is not None
    resp = client.post(
        "/api/v1/auth/password/reset", json={"token": found[1], "new_password": SENHA_NOVA}
    )
    assert resp.status_code == 400


def test_sem_smtp_nao_cria_link(client: TestClient) -> None:
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.user import PasswordReset

    os.environ.pop("SMTP_HOST", None)
    with Session(get_engine()) as session:
        before = session.scalar(select(func.count()).select_from(PasswordReset))
    resp = client.post("/api/v1/auth/password/forgot", json={"email": "ana@empresa.com"})
    assert resp.status_code == 202
    with Session(get_engine()) as session:
        assert session.scalar(select(func.count()).select_from(PasswordReset)) == before
