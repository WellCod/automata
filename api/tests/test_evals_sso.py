"""Evals do login por SSO (ADR-0042) com provedores falsos em situações de produção.

- Provedor com chave ES256 e claim de papel aninhado, no formato do Clerk.
- O provedor troca a chave: o `kid` novo força buscar o JWKS de novo, sem reiniciar a API.
- `id_token` com duas audiências só vale com `azp` deste cliente.
- Discovery com outro issuer, JWKS fora do ar e provedor apontando para a rede interna
  viram 401 ou 502 com mensagem, nunca 500.
- O login por SSO não entra na trilha de auditoria e a sessão emitida passa no /me.
"""

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
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

ISSUER = "https://clerk.empresa.example.com"
CLIENT = "painel"


def _jwt_keys() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
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


class EcIdp:
    """Provedor com ES256, como o Clerk e outros que assinam com curva elíptica."""

    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.kid = "ec-1"
        self.nonce = ""
        self.claims: dict[str, Any] = {}
        self.issuer_in_discovery = ISSUER
        self.jwks_down = False
        self.jwks_calls = 0

    def jwk(self) -> dict[str, Any]:
        data = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.key.public_key()))
        return {**data, "kid": self.kid, "use": "sig", "alg": "ES256"}

    def rotate(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.kid = f"ec-{uuid.uuid4().hex[:6]}"

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(
                200,
                json={
                    "issuer": self.issuer_in_discovery,
                    "authorization_endpoint": f"{ISSUER}/oauth/authorize",
                    "token_endpoint": f"{ISSUER}/oauth/token",
                    "jwks_uri": f"{ISSUER}/.well-known/jwks.json",
                    "token_endpoint_auth_methods_supported": ["client_secret_post"],
                },
            )
        if path == "/.well-known/jwks.json":
            self.jwks_calls += 1
            if self.jwks_down:
                return httpx.Response(503)
            return httpx.Response(200, json={"keys": [self.jwk()]})
        if path == "/oauth/token":
            form = parse_qs(request.content.decode())
            assert form["client_secret"] == ["segredo"]
            now = int(time.time())
            claims = {
                "iss": ISSUER,
                "aud": CLIENT,
                "iat": now,
                "exp": now + 300,
                "nonce": self.nonce,
                **self.claims,
            }
            token = jwt.encode(claims, self.key, algorithm="ES256", headers={"kid": self.kid})
            return httpx.Response(200, json={"id_token": token})
        return httpx.Response(404)


@pytest.fixture(scope="module")
def db() -> Generator[None, None, None]:
    private, public = _jwt_keys()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": private,
            "JWT_PUBLIC_KEY": public,
            "DEMO_REPLAY": "true",
            "OIDC_ISSUER": ISSUER,
            "OIDC_CLIENT_ID": CLIENT,
            "OIDC_CLIENT_SECRET": "segredo",
            "OIDC_REDIRECT_URI": "https://painel.example.com/api/auth/oidc/callback",
            "OIDC_LABEL": "Clerk",
            # formato do Clerk: papel em public_metadata pelos custom claims da sessão
            "OIDC_ROLE_CLAIM": "public_metadata.role",
            "OIDC_ROLE_MAP": "admin=owner,dev=editor,leitura=viewer",
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
def idp(db: None, monkeypatch: pytest.MonkeyPatch) -> EcIdp:
    from app import oidc

    fake = EcIdp()
    oidc.reset_cache()
    transport = httpx.MockTransport(fake.handler)
    monkeypatch.setattr(oidc, "_http", lambda: httpx.Client(transport=transport))
    return fake


@pytest.fixture
def client(idp: EcIdp) -> Generator[TestClient, None, None]:
    from app.main import create_app

    app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, idp: EcIdp, **claims: Any) -> httpx.Response:
    started = client.post("/api/v1/auth/oidc/start")
    if started.status_code != 200:
        return started
    query = parse_qs(urlsplit(started.json()["url"]).query)
    idp.nonce = query["nonce"][0]
    idp.claims = claims
    return client.post("/api/v1/auth/oidc/callback", json={"code": "x", "state": query["state"][0]})


def _person(role: str | None = "dev") -> dict[str, Any]:
    u = uuid.uuid4().hex[:8]
    claims: dict[str, Any] = {
        "sub": f"user_{u}",
        "email": f"{u}@empresa.com",
        "email_verified": True,
    }
    if role is not None:
        claims["public_metadata"] = {"role": role}
    return claims


def test_es256_com_papel_aninhado(client: TestClient, idp: EcIdp) -> None:
    resp = _login(client, idp, **_person("admin"))
    assert resp.status_code == 200, resp.text
    me = client.get(
        "/api/v1/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}
    ).json()
    assert me["role"] == "owner"
    # sem papel mapeado e sem padrão: recusado
    assert _login(client, idp, **_person(None)).status_code == 403


def test_chave_trocada_no_provedor_busca_o_jwks_de_novo(client: TestClient, idp: EcIdp) -> None:
    assert _login(client, idp, **_person()).status_code == 200
    calls = idp.jwks_calls
    idp.rotate()
    resp = _login(client, idp, **_person())
    assert resp.status_code == 200, resp.text
    assert idp.jwks_calls == calls + 1


def test_duas_audiencias_so_com_azp_deste_cliente(client: TestClient, idp: EcIdp) -> None:
    sem_azp = _login(client, idp, **_person(), aud=[CLIENT, "outro"])
    assert sem_azp.status_code == 401
    com_azp = _login(client, idp, **_person(), aud=[CLIENT, "outro"], azp=CLIENT)
    assert com_azp.status_code == 200, com_azp.text


def test_discovery_com_outro_issuer_e_jwks_fora_do_ar(client: TestClient, idp: EcIdp) -> None:
    from app import oidc

    idp.issuer_in_discovery = "https://atacante.example.com"
    oidc.reset_cache()
    resp = client.post("/api/v1/auth/oidc/start")
    assert resp.status_code == 502
    assert "issuer" in resp.json()["detail"]

    idp.issuer_in_discovery = ISSUER
    oidc.reset_cache()
    idp.jwks_down = True
    resp = _login(client, idp, **_person())
    assert resp.status_code == 401
    assert "fora do ar" in resp.json()["detail"]


def test_provedor_na_rede_interna_e_barrado(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    from app import oidc
    from app.main import create_app

    # sem o MockTransport: o guarded_client de verdade resolve e confere o IP
    monkeypatch.setenv("OIDC_ISSUER", "https://localhost:9443")
    get_settings.cache_clear()
    oidc.reset_cache()
    try:
        app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
        with TestClient(app) as c:
            resp = c.post("/api/v1/auth/oidc/start")
        assert resp.status_code == 502
    finally:
        monkeypatch.setenv("OIDC_ISSUER", ISSUER)
        get_settings.cache_clear()
        oidc.reset_cache()


def test_login_por_sso_fora_da_trilha(client: TestClient, idp: EcIdp) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.audit import AuditEvent

    assert _login(client, idp, **_person()).status_code == 200
    with Session(get_engine()) as session:
        actions = list(session.scalars(select(AuditEvent.action)))
    assert not [a for a in actions if "/auth/" in a]
