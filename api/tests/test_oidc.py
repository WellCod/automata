"""Login por SSO via OIDC (ADR-0042) contra um provedor falso servido por MockTransport."""

import json
import os
import time
import uuid
from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

# segredo do navegador que o BFF gera e guarda no cookie (Fase 49)
KEY = "segredo-do-navegador-" + "x" * 24
START = {"browser_key": KEY}

ISSUER = "https://idp.example.com"
CLIENT = "automata-painel"


def _rsa() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem(key: rsa.RSAPrivateKey) -> tuple[str, str]:
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


class FakeIdp:
    """Provedor OIDC mínimo: discovery, JWKS e token endpoint."""

    def __init__(self) -> None:
        self.key = _rsa()
        self.kid = "k1"
        self.claims: dict[str, Any] = {}
        self.nonce = ""
        self.sign_with: rsa.RSAPrivateKey | None = None
        self.alg = "RS256"
        self.token_calls: list[dict[str, list[str]]] = []

    def jwk(self) -> dict[str, Any]:
        data = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        return {**data, "kid": self.kid, "use": "sig", "alg": "RS256"}

    def id_token(self) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT,
            "iat": now,
            "exp": now + 300,
            "nonce": self.nonce,
            **self.claims,
        }
        if self.alg == "none":
            return jwt.encode(claims, None, algorithm="none")
        if self.alg == "HS256":
            return jwt.encode(claims, "segredo-do-cliente", algorithm="HS256")
        return jwt.encode(
            claims, self.sign_with or self.key, algorithm="RS256", headers={"kid": self.kid}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": f"{ISSUER}/authorize",
                    "token_endpoint": f"{ISSUER}/token",
                    "jwks_uri": f"{ISSUER}/jwks",
                },
            )
        if path == "/jwks":
            return httpx.Response(200, json={"keys": [self.jwk()]})
        if path == "/token":
            self.token_calls.append(parse_qs(request.content.decode()))
            return httpx.Response(200, json={"id_token": self.id_token()})
        return httpx.Response(404)


@pytest.fixture(scope="module")
def db_and_keys() -> Generator[None, None, None]:
    private, public = _pem(_rsa())
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": private,
            "JWT_PUBLIC_KEY": public,
            "DEMO_REPLAY": "true",
            "OIDC_ISSUER": ISSUER,
            "OIDC_CLIENT_ID": CLIENT,
            "OIDC_CLIENT_SECRET": "segredo-do-cliente",
            "OIDC_REDIRECT_URI": "https://painel.example.com/api/auth/oidc/callback",
            "OIDC_LABEL": "Empresa",
            "OIDC_ROLE_CLAIM": "groups",
            "OIDC_ROLE_MAP": "plataforma=owner,produto=editor",
            "OIDC_DEFAULT_ROLE": "viewer",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


@pytest.fixture
def idp(db_and_keys: None, monkeypatch: pytest.MonkeyPatch) -> FakeIdp:
    from app import oidc

    fake = FakeIdp()
    oidc.reset_cache()
    monkeypatch.setattr(
        oidc, "_http", lambda: httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    return fake


@pytest.fixture
def client(idp: FakeIdp) -> Generator[TestClient, None, None]:
    from app.main import create_app

    app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, idp: FakeIdp, **claims: Any) -> httpx.Response:
    started = client.post("/api/v1/auth/oidc/start", json=START)
    assert started.status_code == 200, started.text
    query = parse_qs(urlsplit(started.json()["url"]).query)
    assert query["code_challenge_method"] == ["S256"]
    idp.nonce = query["nonce"][0]
    idp.claims = claims
    return client.post(
        "/api/v1/auth/oidc/callback",
        json={"code": "c-1", "state": query["state"][0], "browser_key": KEY},
    )


def _me(client: TestClient, token: str) -> dict[str, Any]:
    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    data: dict[str, Any] = resp.json()
    return data


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_info_publica(client: TestClient) -> None:
    info = client.get("/api/v1/auth/oidc").json()
    assert info == {"enabled": True, "label": "Empresa", "password_login": True}


def test_primeiro_login_cria_conta_com_papel_do_grupo(client: TestClient, idp: FakeIdp) -> None:
    u = _uid()
    resp = _login(
        client,
        idp,
        sub=f"s-{u}",
        email=f"{u}@empresa.com",
        email_verified=True,
        groups=["produto", "outro"],
    )
    assert resp.status_code == 200, resp.text
    me = _me(client, resp.json()["access_token"])
    assert me["email"] == f"{u}@empresa.com"
    assert me["role"] == "editor"
    # o segredo vai por basic auth e o verificador do PKCE na troca
    assert "code_verifier" in idp.token_calls[-1]
    assert "client_secret" not in idp.token_calls[-1]


def test_state_vale_uma_vez(client: TestClient, idp: FakeIdp) -> None:
    started = client.post("/api/v1/auth/oidc/start", json=START).json()
    query = parse_qs(urlsplit(started["url"]).query)
    idp.nonce = query["nonce"][0]
    idp.claims = {"sub": f"s-{_uid()}", "email": f"{_uid()}@empresa.com", "email_verified": True}
    body = {"code": "c", "state": query["state"][0], "browser_key": KEY}
    assert client.post("/api/v1/auth/oidc/callback", json=body).status_code == 200
    assert client.post("/api/v1/auth/oidc/callback", json=body).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/oidc/callback",
            json={"code": "c", "state": "inventado", "browser_key": KEY},
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "falha", ["outra_chave", "aud", "nonce", "none", "hs256", "vencido", "iss"]
)
def test_id_token_adulterado_e_recusado(client: TestClient, idp: FakeIdp, falha: str) -> None:
    claims: dict[str, Any] = {
        "sub": f"s-{_uid()}",
        "email": f"{_uid()}@empresa.com",
        "email_verified": True,
    }
    if falha == "outra_chave":
        idp.sign_with = _rsa()
    elif falha == "aud":
        claims["aud"] = "outro-cliente"
    elif falha == "none":
        idp.alg = "none"
    elif falha == "hs256":
        idp.alg = "HS256"
    elif falha == "vencido":
        claims["exp"] = int(time.time()) - 3600
    elif falha == "iss":
        claims["iss"] = "https://outro.example.com"
    started = client.post("/api/v1/auth/oidc/start", json=START).json()
    query = parse_qs(urlsplit(started["url"]).query)
    idp.nonce = "nonce-trocado" if falha == "nonce" else query["nonce"][0]
    idp.claims = claims
    resp = client.post(
        "/api/v1/auth/oidc/callback",
        json={"code": "c", "state": query["state"][0], "browser_key": KEY},
    )
    assert resp.status_code == 401, resp.text


def _local_user(client: TestClient, email: str, role: str = "editor") -> str:
    from app.auth import issue_token

    owner = {"Authorization": f"Bearer {issue_token('owner-sso', ['agent_os:admin'])}"}
    resp = client.post(
        "/api/v1/users",
        json={"email": email, "password": "Senha-Forte-12345", "role": role},
        headers=owner,
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def test_email_nao_verificado_nao_toma_conta_existente(client: TestClient, idp: FakeIdp) -> None:
    email = f"{_uid()}@empresa.com"
    _local_user(client, email)
    resp = _login(client, idp, sub=f"s-{_uid()}", email=email, email_verified=False)
    assert resp.status_code == 403


def test_conta_existente_ligada_por_email_e_depois_pelo_sujeito(
    client: TestClient, idp: FakeIdp
) -> None:
    email = f"{_uid()}@empresa.com"
    user_id = _local_user(client, email)
    sub = f"s-{_uid()}"
    first = _login(client, idp, sub=sub, email=email, email_verified=True)
    assert first.status_code == 200, first.text
    assert _me(client, first.json()["access_token"])["id"] == user_id
    # o e-mail mudou no provedor: a conta segue pelo sujeito
    second = _login(client, idp, sub=sub, email=f"novo-{email}", email_verified=True)
    assert _me(client, second.json()["access_token"])["id"] == user_id


def test_conta_desativada_nao_entra(client: TestClient, idp: FakeIdp) -> None:
    from app.auth import issue_token

    email = f"{_uid()}@empresa.com"
    user_id = _local_user(client, email)
    owner = {"Authorization": f"Bearer {issue_token('owner-sso', ['agent_os:admin'])}"}
    client.patch(f"/api/v1/users/{user_id}", json={"is_active": False}, headers=owner)
    resp = _login(client, idp, sub=f"s-{_uid()}", email=email, email_verified=True)
    assert resp.status_code == 403


def test_papel_sincronizado_e_ultimo_owner_mantido(client: TestClient, idp: FakeIdp) -> None:
    from sqlalchemy import update
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.user import User, UserRole

    sub, email = f"s-{_uid()}", f"{_uid()}@empresa.com"
    first = _login(client, idp, sub=sub, email=email, email_verified=True, groups=["plataforma"])
    assert _me(client, first.json()["access_token"])["role"] == "owner"
    with Session(get_engine()) as session:
        # só ele de owner ativo
        session.execute(
            update(User)
            .where(User.email != email, User.role == UserRole.owner)
            .values(is_active=False)
        )
        session.commit()
    kept = _login(client, idp, sub=sub, email=email, email_verified=True, groups=["produto"])
    assert _me(client, kept.json()["access_token"])["role"] == "owner"

    other_sub, other = f"s-{_uid()}", f"{_uid()}@empresa.com"
    _login(client, idp, sub=other_sub, email=other, email_verified=True, groups=["plataforma"])
    demoted = _login(client, idp, sub=sub, email=email, email_verified=True, groups=["produto"])
    # o token novo vale mesmo com o corte de sessão no mesmo segundo
    assert _me(client, demoted.json()["access_token"])["role"] == "editor"


def test_sem_papel_e_dominio_fora(
    client: TestClient, idp: FakeIdp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OIDC_DEFAULT_ROLE", "")
    monkeypatch.setenv("OIDC_ALLOWED_DOMAINS", "empresa.com")
    get_settings.cache_clear()
    try:
        sem = _login(
            client, idp, sub=f"s-{_uid()}", email=f"{_uid()}@empresa.com", email_verified=True
        )
        assert sem.status_code == 403
        fora = _login(
            client,
            idp,
            sub=f"s-{_uid()}",
            email=f"{_uid()}@gmail.com",
            email_verified=True,
            groups=["produto"],
        )
        assert fora.status_code == 403
    finally:
        monkeypatch.delenv("OIDC_ALLOWED_DOMAINS")
        monkeypatch.setenv("OIDC_DEFAULT_ROLE", "viewer")
        get_settings.cache_clear()


def test_login_por_senha_desligado_e_conta_sso_sem_senha(
    client: TestClient, idp: FakeIdp, monkeypatch: pytest.MonkeyPatch
) -> None:
    sso_email = f"{_uid()}@empresa.com"
    _login(client, idp, sub=f"s-{_uid()}", email=sso_email, email_verified=True)
    refused = client.post(
        "/api/v1/auth/login", json={"email": sso_email, "password": "qualquer-coisa"}
    )
    assert refused.status_code == 401

    editor = f"{_uid()}@empresa.com"
    owner = f"{_uid()}@empresa.com"
    _local_user(client, editor, "editor")
    _local_user(client, owner, "owner")
    monkeypatch.setenv("PASSWORD_LOGIN", "false")
    get_settings.cache_clear()
    try:
        body = {"password": "Senha-Forte-12345"}
        assert client.post("/api/v1/auth/login", json={**body, "email": editor}).status_code == 401
        assert client.post("/api/v1/auth/login", json={**body, "email": owner}).status_code == 200
    finally:
        monkeypatch.delenv("PASSWORD_LOGIN")
        get_settings.cache_clear()


def test_code_e_state_vazados_sem_o_segredo_do_navegador(client: TestClient, idp: FakeIdp) -> None:
    started = client.post("/api/v1/auth/oidc/start", json=START).json()
    query = parse_qs(urlsplit(started["url"]).query)
    idp.nonce = query["nonce"][0]
    idp.claims = {"sub": f"s-{_uid()}", "email": f"{_uid()}@empresa.com", "email_verified": True}
    stolen = {"code": "c", "state": query["state"][0], "browser_key": "outro-" + "y" * 40}
    assert client.post("/api/v1/auth/oidc/callback", json=stolen).status_code == 401
    # o state foi consumido: nem o dono consegue reaproveitar
    real = {**stolen, "browser_key": KEY}
    assert client.post("/api/v1/auth/oidc/callback", json=real).status_code == 401


def test_conta_nova_e_dominio_so_com_email_verificado(
    client: TestClient, idp: FakeIdp, monkeypatch: pytest.MonkeyPatch
) -> None:
    nova = _login(
        client, idp, sub=f"s-{_uid()}", email=f"{_uid()}@empresa.com", email_verified=False
    )
    assert nova.status_code == 403
    monkeypatch.setenv("OIDC_ALLOWED_DOMAINS", "empresa.com")
    get_settings.cache_clear()
    try:
        ceo = _login(client, idp, sub=f"s-{_uid()}", email="ceo@empresa.com", email_verified=False)
        assert ceo.status_code == 403
        assert ceo.json()["detail"] == "Domínio de e-mail não autorizado"
    finally:
        monkeypatch.delenv("OIDC_ALLOWED_DOMAINS")
        get_settings.cache_clear()


def test_email_com_maiuscula_cadastrado_pelo_owner_e_ligado(
    client: TestClient, idp: FakeIdp
) -> None:
    u = _uid()
    user_id = _local_user(client, f"Fulano.{u}@Empresa.com")
    resp = _login(client, idp, sub=f"s-{u}", email=f"fulano.{u}@empresa.com", email_verified=True)
    assert resp.status_code == 200, resp.text
    assert _me(client, resp.json()["access_token"])["id"] == user_id
