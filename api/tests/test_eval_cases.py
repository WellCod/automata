"""Casos de teste por agente e time: checagens e CRUD (ADR-0015)."""

import os
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import ValidationError
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.models.user import UserRole
from app.schemas.eval import EvalCaseInput, TextCheck
from app.schemas.user import ROLE_SCOPES
from app.settings import get_settings

TEXT = {"type": "text", "kind": "contains", "value": "prazo"}
TOOLS = {"type": "tools", "tools": ["buscar_politicas_atendimento"]}
JUDGE = {"type": "judge", "criteria": "Responde com o prazo e cita a política de troca"}


def _case(name: str = "prazo de troca", **extra: Any) -> dict[str, Any]:
    return {"name": name, "input": "Qual o prazo para trocar?", "checks": [TEXT], **extra}


# --- checagens ---


def test_caso_com_os_tres_tipos() -> None:
    case = EvalCaseInput.model_validate(_case(checks=[TEXT, TOOLS, JUDGE]))
    assert [c.type for c in case.checks] == ["text", "tools", "judge"]
    judge = case.checks[2]
    assert judge.type == "judge" and judge.mode == "binary" and judge.threshold == 7


@pytest.mark.parametrize(
    ("checks", "trecho"),
    [
        ([], "at least 1"),
        ([TEXT] * 6, "at most 5"),
        ([{"type": "text", "kind": "contains", "value": "  "}], "precisa de um texto"),
        ([{"type": "text", "kind": "always"}], "kind"),
        ([TOOLS, TOOLS], "no máximo uma checagem do tipo tools"),
        ([JUDGE, JUDGE], "no máximo uma checagem do tipo judge"),
        ([{"type": "tools", "tools": ["a", "a"]}], "tool repetida"),
        ([{"type": "tools", "tools": ["rm -rf"]}], "pattern"),
        ([{"type": "judge", "criteria": "curto"}], "at least 10"),
        ([{**JUDGE, "mode": "numeric", "threshold": 11}], "less than or equal to 10"),
    ],
)
def test_checagens_invalidas(checks: list[dict[str, Any]], trecho: str) -> None:
    with pytest.raises(ValidationError, match=trecho):
        EvalCaseInput.model_validate(_case(checks=checks))


def test_texto_vira_a_regra_dos_workflows() -> None:
    rule = TextCheck(kind="not_contains", value="garantia").rule()
    assert (rule.kind, rule.source, rule.value) == ("not_contains", "previous", "garantia")


def test_papeis() -> None:
    assert "evals:read" in ROLE_SCOPES[UserRole.viewer]
    assert "evals:write" not in ROLE_SCOPES[UserRole.viewer]
    assert {"evals:read", "evals:write", "evals:run"} <= set(ROLE_SCOPES[UserRole.editor])


# --- CRUD, com Postgres ---


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
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


def _config(client: TestClient, kind: str, name: str) -> str:
    resp = client.post(
        "/api/v1/configs", json={"name": name, "description": f"Use para {name}", "kind": kind}
    )
    resp.raise_for_status()
    return str(resp.json()["id"])


def test_crud_de_casos(client: TestClient) -> None:
    agent = _config(client, "agent", "atendimento")
    base = f"/api/v1/configs/{agent}/eval-cases"
    assert client.get(base).json() == []

    first = client.post(base, json=_case(checks=[TEXT, TOOLS]))
    assert first.status_code == 201, first.text
    second = client.post(base, json=_case("tom cordial", checks=[JUDGE]))
    assert second.status_code == 201
    assert [c["name"] for c in client.get(base).json()] == ["prazo de troca", "tom cordial"]
    assert [c["position"] for c in client.get(base).json()] == [0, 1]
    assert first.json()["checks"][1] == {
        "type": "tools",
        "tools": ["buscar_politicas_atendimento"],
        "allow_additional": True,
    }

    assert client.post(base, json=_case()).status_code == 409
    case_id = second.json()["id"]
    assert client.put(f"{base}/{case_id}", json=_case()).status_code == 409
    updated = client.put(f"{base}/{case_id}", json=_case("tom cordial", input="Oi"))
    assert updated.status_code == 200 and updated.json()["input"] == "Oi"
    assert updated.json()["checks"] == [{"type": "text", "kind": "contains", "value": "prazo"}]

    assert client.delete(f"{base}/{case_id}").status_code == 204
    assert client.delete(f"{base}/{case_id}").status_code == 404
    assert len(client.get(base).json()) == 1


def test_casos_sao_de_cada_config(client: TestClient) -> None:
    a = _config(client, "agent", "a")
    b = _config(client, "team", "time b")
    created = client.post(f"/api/v1/configs/{a}/eval-cases", json=_case()).json()
    # mesmo nome em outra config pode; caso de A não aparece nem muda por B
    assert client.post(f"/api/v1/configs/{b}/eval-cases", json=_case()).status_code == 201
    assert client.delete(f"/api/v1/configs/{b}/eval-cases/{created['id']}").status_code == 404
    assert (
        client.get("/api/v1/configs/00000000-0000-0000-0000-000000000000/eval-cases").status_code
        == 404
    )


def test_workflow_e_limite(client: TestClient) -> None:
    wf = _config(client, "workflow", "fluxo")
    resp = client.post(f"/api/v1/configs/{wf}/eval-cases", json=_case())
    assert resp.status_code == 422 and "Workflow" in resp.json()["detail"]

    agent = _config(client, "agent", "muitos")
    for i in range(50):
        client.post(f"/api/v1/configs/{agent}/eval-cases", json=_case(f"c{i}")).raise_for_status()
    resp = client.post(f"/api/v1/configs/{agent}/eval-cases", json=_case("c50"))
    assert resp.status_code == 422 and "50" in resp.json()["detail"]
