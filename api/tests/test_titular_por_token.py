"""Pedido do titular por token de integração e pelo próprio usuário do painel (ADR-0036)."""

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.test_integrations import _bearer, _keys


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


def _owner() -> dict[str, str]:
    from app.auth import issue_token

    return _bearer(issue_token("owner", ["agent_os:admin"]))


def _token(client: TestClient, name: str, data_subjects: bool) -> dict[str, str]:
    agent = client.post(
        "/api/v1/configs", json={"name": f"a {name}", "description": "x"}, headers=_owner()
    ).json()["id"]
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={"name": f"a {name}", "description": "x", "payload": {"model_id": "claude-haiku-4-5"}},
        headers=_owner(),
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish", headers=_owner()).raise_for_status()
    issued = client.post(
        "/api/v1/integrations",
        json={"name": name, "agent_ids": [agent], "data_subjects": data_subjects},
        headers=_owner(),
    )
    assert issued.status_code == 201, issued.text
    assert issued.json()["data_subjects"] is data_subjects
    return _bearer(issued.json()["token"])


def test_token_sem_a_opcao_nao_pede(client: TestClient) -> None:
    plain = _token(client, "sem", False)
    assert client.get("/api/v1/data-subjects/ana", headers=plain).status_code == 403
    assert client.post("/api/v1/data-subjects/ana/export", headers=plain).status_code == 403


def test_token_pede_e_ve_so_os_proprios_pedidos(client: TestClient) -> None:
    loja = _token(client, "loja", True)
    banco = _token(client, "banco", True)
    assert client.get("/api/v1/data-subjects/ana", headers=loja).status_code == 200
    mine = client.post("/api/v1/data-subjects/ana/export", headers=loja).json()
    assert mine["source"] == "integration"
    other = client.post("/api/v1/data-subjects/bia/export", headers=banco).json()

    listed = {r["id"] for r in client.get("/api/v1/data-subject-requests", headers=loja).json()}
    assert mine["id"] in listed and other["id"] not in listed
    assert (
        client.get(
            f"/api/v1/data-subject-requests/{other['id']}/download", headers=loja
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/data-subject-requests/{mine['id']}/download", headers=loja).status_code
        == 200
    )
    # o owner vê todos
    everyone = {
        r["id"] for r in client.get("/api/v1/data-subject-requests", headers=_owner()).json()
    }
    assert {mine["id"], other["id"]} <= everyone
    # nem o token com a opção mexe no piso ou nos usuários
    assert client.get("/api/v1/instance-guardrails", headers=loja).status_code == 403


def test_usuario_do_painel_pede_os_proprios_dados(client: TestClient) -> None:
    from sqlalchemy.orm import Session

    from app.auth import issue_token
    from app.db import get_engine
    from app.models.user import User, UserRole
    from app.schemas.user import ROLE_SCOPES

    user_id = uuid4()
    with Session(get_engine()) as session:
        session.add(
            User(
                id=user_id,
                email="carla@empresa.com",
                hashed_password="x",
                role=UserRole.viewer,
            )
        )
        session.commit()
    me = _bearer(issue_token(str(user_id), ROLE_SCOPES[UserRole.viewer]))

    assert client.get("/api/v1/me/data", headers=me).json()["user_id"] == str(user_id)
    exported = client.post("/api/v1/me/data/export", headers=me)
    assert exported.status_code == 202 and exported.json()["source"] == "self"
    request_id = exported.json()["id"]
    assert (
        client.get(f"/api/v1/me/data/requests/{request_id}/download", headers=me).status_code == 200
    )
    # o viewer não usa as rotas do owner
    assert client.get("/api/v1/data-subject-requests", headers=me).status_code == 403

    wrong = client.post("/api/v1/me/data/erase", json={"confirm": "outra@x.com"}, headers=me)
    assert wrong.status_code == 422
    erased = client.post("/api/v1/me/data/erase", json={"confirm": "CARLA@empresa.com"}, headers=me)
    assert erased.status_code == 202
    kinds = [r["kind"] for r in client.get("/api/v1/me/data/requests", headers=me).json()]
    assert sorted(kinds) == ["erase", "export"]
    # a conta continua
    with Session(get_engine()) as session:
        assert session.get(User, user_id) is not None

    # token de integração não usa as rotas do próprio usuário
    loja = _token(client, "loja2", True)
    assert client.get("/api/v1/me/data", headers=loja).status_code == 401
