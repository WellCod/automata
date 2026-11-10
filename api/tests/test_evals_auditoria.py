"""Evals da trilha de auditoria (ADR-0041) com autenticação de verdade.

- Uma bateria de escritas com segredo, senha e prompt não deixa nenhum deles na tabela.
- Criar e rebaixar usuário e emitir token entram com o autor e o antes e o depois.
- A decisão de aprovação pelo `continue` do AgentOS entra, mesmo recusada.
- A exclusão do titular troca o id dele pelo pseudônimo nas linhas em que ele agiu.
- Leitura pura e login não entram.
"""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

PROMPT = "prompt-confidencial-5512"
HEADER = "Bearer cabecalho-secreto-9021"
PASSWORD = "Senha-de-teste-forte-4471!"


def _pair() -> tuple[str, str]:
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


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    private, public = _pair()
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "JWT_PRIVATE_KEY": private,
            "JWT_PUBLIC_KEY": public,
            "DEMO_REPLAY": "true",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        app = create_app(auto_provision_dbs=True, enable_auth=True, enable_mcp_server=False)
        with TestClient(app) as c:
            yield c
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _h(sub: str, scopes: list[str]) -> dict[str, str]:
    from app.auth import issue_token

    return {"Authorization": f"Bearer {issue_token(sub, scopes)}"}


def _owner() -> dict[str, str]:
    return _h("owner-1", ["agent_os:admin"])


def _viewer(sub: str) -> dict[str, str]:
    from app.models.user import UserRole
    from app.schemas.user import ROLE_SCOPES

    return _h(sub, list(ROLE_SCOPES[UserRole.viewer]))


def _rows() -> list[dict[str, object]]:
    from app.db import get_engine
    from app.models.audit import AuditEvent

    with Session(get_engine()) as session:
        return [
            {"actor": e.actor, "action": e.action, "status": e.status_code, "detail": e.detail}
            for e in session.scalars(select(AuditEvent).order_by(AuditEvent.created_at))
        ]


def _dump() -> str:
    from app.db import get_engine

    with Session(get_engine()) as session:
        return str(
            session.execute(
                text("SELECT coalesce(string_agg(audit_event::text, '|'), '') FROM audit_event")
            ).scalar()
        )


def test_bateria_de_escritas_sem_segredo_na_trilha(client: TestClient) -> None:
    owner = _owner()
    config = client.post(
        "/api/v1/configs", json={"name": "segredos", "description": "x"}, headers=owner
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{config}/draft",
        json={
            "name": "segredos",
            "description": "x",
            "payload": {"model_id": "gpt-4o", "instructions": {"persona": PROMPT}},
        },
        headers=owner,
    ).raise_for_status()
    server = client.post(
        "/api/v1/mcp-servers",
        json={
            "name": "crm",
            "slug": "crm",
            "url": "https://crm.example.com/mcp",
            "headers": {"Authorization": HEADER},
        },
        headers=owner,
    )
    # host que não resolve dá 422; a escrita entra do mesmo jeito, sem o cabeçalho
    assert server.status_code in (201, 422), server.text
    user = client.post(
        "/api/v1/users",
        json={"email": "nova@exemplo.com", "password": PASSWORD, "role": "editor"},
        headers=owner,
    )
    assert user.status_code == 201, user.text
    client.post(f"/api/v1/configs/{config}/publish", headers=owner).raise_for_status()
    issued = client.post(
        "/api/v1/integrations",
        json={"name": "crm externo", "agent_ids": [config]},
        headers=owner,
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()["token"]

    dump = _dump()
    for secret in (PROMPT, HEADER, PASSWORD, token, "nova@exemplo.com"):
        assert secret not in dump
    actions = [str(r["action"]) for r in _rows()]
    assert "POST /api/v1/mcp-servers" in actions
    assert "POST /api/v1/users" in actions
    assert "POST /api/v1/integrations" in actions


def test_rebaixar_usuario_guarda_o_papel_antes_e_depois(client: TestClient) -> None:
    owner = _owner()
    user = client.post(
        "/api/v1/users",
        json={"email": "rebaixar@exemplo.com", "password": PASSWORD, "role": "editor"},
        headers=owner,
    ).json()
    patched = client.patch(f"/api/v1/users/{user['id']}", json={"role": "viewer"}, headers=owner)
    assert patched.status_code == 200, patched.text
    row = [r for r in _rows() if r["action"] == "PATCH /api/v1/users/{user_id}"][-1]
    assert row["actor"] == "owner-1"
    assert row["detail"] == {
        "before": {"role": "editor", "is_active": True},
        "after": {"role": "viewer", "is_active": True},
    }


def test_continue_de_aprovacao_entra_mesmo_recusado(client: TestClient) -> None:
    resp = client.post(
        "/agents/nao-existe/runs/run-1/continue",
        data={"tools": "[]", "stream": "false"},
        headers=_viewer("revisora"),
    )
    assert resp.status_code >= 400
    row = [r for r in _rows() if str(r["action"]).endswith("/continue")][-1]
    assert row["actor"] == "revisora"
    assert row["status"] == resp.status_code


def test_leitura_e_login_ficam_de_fora(client: TestClient) -> None:
    before = len(_rows())
    client.get("/api/v1/configs", headers=_owner())
    client.get("/api/v1/audit", headers=_owner())
    client.post("/api/v1/auth/login", json={"email": "x@exemplo.com", "password": "errada"})
    assert len(_rows()) == before


def test_exclusao_do_titular_troca_o_autor_pelo_pseudonimo(client: TestClient) -> None:
    from app.data_subjects import pseudonym

    config = client.post(
        "/api/v1/configs", json={"name": "titular", "description": "x"}, headers=_owner()
    ).json()["id"]
    denied = client.post(f"/api/v1/configs/{config}/publish", headers=_viewer("cliente-77"))
    assert denied.status_code == 403
    assert any(r["actor"] == "cliente-77" for r in _rows())

    erased = client.post(
        "/api/v1/data-subjects/cliente-77/erase",
        json={"confirm": "cliente-77"},
        headers=_owner(),
    )
    assert erased.status_code == 202, erased.text
    actors = {r["actor"] for r in _rows()}
    assert "cliente-77" not in actors
    assert pseudonym("cliente-77") in actors
    assert "cliente-77" not in _dump()
