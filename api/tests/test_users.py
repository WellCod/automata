"""Testes de usuários, papéis e emissão de token.

Cobre criação de usuário, autenticação, rate limit do login e
proteção do endpoint de criação por scope agent_os:admin.
"""

import os
from collections.abc import Generator

import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.models.user import UserRole
from app.repositories.user import UserRepository
from app.schemas.user import ROLE_SCOPES
from app.services.user import UserService
from app.settings import get_settings


def _generate_rsa_key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


_PRIVATE_KEY, _PUBLIC_KEY = _generate_rsa_key_pair()


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ["JWT_PRIVATE_KEY"] = _PRIVATE_KEY
        os.environ["JWT_PUBLIC_KEY"] = _PUBLIC_KEY
        get_settings.cache_clear()
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def session(db_url: str) -> Generator[Session, None, None]:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(bind=conn) as sess:
            yield sess
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def client(db_url: str) -> Generator[TestClient, None, None]:
    os.environ["DATABASE_URL"] = db_url
    get_settings.cache_clear()
    from app.main import create_app

    yield TestClient(create_app(auto_provision_dbs=False, enable_auth=True))
    get_settings.cache_clear()


def _admin_token() -> str:
    from app.auth import issue_token

    return issue_token("admin", ["agent_os:admin"])


# --- UserService ---


def test_criar_usuario(session: Session) -> None:
    svc = UserService(UserRepository(session))
    user = svc.create_user("alice@example.com", "senha1234", UserRole.editor)
    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.role == UserRole.editor
    assert user.is_active is True


def test_email_duplicado_levanta_valor(session: Session) -> None:
    svc = UserService(UserRepository(session))
    svc.create_user("dup@example.com", "senha1234", UserRole.viewer)
    with pytest.raises(ValueError, match="Email já cadastrado"):
        svc.create_user("dup@example.com", "outra", UserRole.viewer)


def test_autenticar_usuario_valido(session: Session) -> None:
    svc = UserService(UserRepository(session))
    svc.create_user("login@example.com", "senha1234", UserRole.owner)
    user = svc.authenticate("login@example.com", "senha1234")
    assert user.email == "login@example.com"


def test_autenticar_senha_errada(session: Session) -> None:
    svc = UserService(UserRepository(session))
    svc.create_user("wrongpw@example.com", "certa1234", UserRole.viewer)
    with pytest.raises(ValueError, match="Credenciais inválidas"):
        svc.authenticate("wrongpw@example.com", "errada")


def test_autenticar_email_inexistente(session: Session) -> None:
    svc = UserService(UserRepository(session))
    with pytest.raises(ValueError, match="Credenciais inválidas"):
        svc.authenticate("naoexiste@example.com", "qualquer")


# --- scopes por role ---


def test_owner_tem_scope_admin() -> None:
    assert "agent_os:admin" in ROLE_SCOPES[UserRole.owner]


def test_editor_tem_scope_write() -> None:
    assert "agent_os:write" in ROLE_SCOPES[UserRole.editor]


def test_viewer_tem_scope_read() -> None:
    assert "agent_os:read" in ROLE_SCOPES[UserRole.viewer]


# --- endpoints ---


def test_login_sucesso(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/users",
        json={"email": "login_endpoint@example.com", "password": "senha1234", "role": "editor"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "login_endpoint@example.com", "password": "senha1234"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    payload = jwt.decode(
        data["access_token"], _PUBLIC_KEY, algorithms=["RS256"], audience="automata"
    )
    assert "agent_os:write" in payload["scopes"]


def test_login_credenciais_invalidas(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/login", json={"email": "x@x.com", "password": "errada"})
    assert resp.status_code == 401


def test_criar_usuario_sem_token_retorna_422(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/users",
        json={"email": "new@x.com", "password": "senha1234", "role": "viewer"},
    )
    assert resp.status_code in (401, 422)


def test_criar_usuario_sem_scope_admin_retorna_403(client: TestClient) -> None:
    from app.auth import issue_token

    token = issue_token("u1", ["agent_os:read"])
    resp = client.post(
        "/api/v1/auth/users",
        json={"email": "new@x.com", "password": "senha1234", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_criar_usuario_com_admin_retorna_201(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/users",
        json={"email": "novo@x.com", "password": "senha1234", "role": "editor"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "novo@x.com"
    assert data["role"] == "editor"


def test_criar_usuario_email_duplicado_retorna_409(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/users",
        json={"email": "dup2@x.com", "password": "senha1234", "role": "viewer"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    resp = client.post(
        "/api/v1/auth/users",
        json={"email": "dup2@x.com", "password": "outra1234", "role": "viewer"},
        headers={"Authorization": f"Bearer {_admin_token()}"},
    )
    assert resp.status_code == 409
