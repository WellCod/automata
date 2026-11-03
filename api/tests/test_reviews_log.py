"""Registro das decisões humanas (ADR-0028): o que entra e quem decidiu."""

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _req(**fields: Any) -> dict[str, Any]:
    return {"step_id": "s1", "step_name": "analise", **fields}


def _stored(req: dict[str, Any], output: str | None = None) -> dict[str, dict[str, Any]]:
    when = "loop" if req.get("step_type") == "Loop" else "after"
    return {"s1": {"step_name": "analise", "when": when, "output": output}}


@pytest.mark.parametrize(
    ("req", "decision"),
    [
        (_req(confirmed=True), "approved"),
        (_req(confirmed=False), "rejected"),
        (_req(confirmed=True, edited_output="novo"), "edited"),
        (_req(confirmed=True, step_type="Loop"), "loop_done"),
        (_req(confirmed=False, step_type="Loop"), "loop_again"),
    ],
)
def test_tipo_da_decisao(req: dict[str, Any], decision: str) -> None:
    from app.agents.reviews import review_entries

    [entry] = review_entries([req], _stored(req), "ana")
    assert (entry["decision"], entry["by"]) == (decision, "ana")


def test_so_o_requisito_ativo_e_pendente_entra() -> None:
    from app.agents.reviews import review_entries

    old = _req(confirmed=False, rejection_feedback="faltou")
    active = _req(confirmed=True)
    assert [e["decision"] for e in review_entries([old, active], _stored(active), None)] == [
        "approved"
    ]
    # sem decisão ou fora das pendências do run, nada entra
    assert review_entries([_req()], _stored(_req()), None) == []
    assert review_entries([active], {}, None) == []
    assert review_entries([active], _stored(active), None)[0]["by"] == "desconhecido"


def test_edicao_guarda_antes_e_depois_mascarados_e_limitados() -> None:
    from app.agents.reviews import REVIEW_TEXT_CHARS, review_entries

    req = _req(
        confirmed=True,
        edited_output="cliente ana@x.io pediu R$ 210" + "x" * (REVIEW_TEXT_CHARS * 2),
    )
    [entry] = review_entries([req], _stored(req, "cliente ana@x.io pediu R$ 120"), "owner")
    assert entry["before"] == "cliente [e-mail removido] pediu R$ 120"
    assert entry["after"].startswith("cliente [e-mail removido] pediu R$ 210")
    assert len(entry["after"]) <= REVIEW_TEXT_CHARS


def test_middleware_guarda_quem_fez_a_request() -> None:
    from app.integrations import RevocationMiddleware, current_actor

    revoked: Any = SimpleNamespace(is_revoked=lambda jti, sub, iat: False)
    app = FastAPI()
    app.add_middleware(RevocationMiddleware, revoked=revoked)

    @app.get("/quem")
    def quem() -> dict[str, str | None]:
        return {"actor": current_actor.get()}

    import jwt

    token = jwt.encode({"sub": "ana", "jti": "j1", "iat": 1}, "segredo", algorithm="HS256")
    client = TestClient(app)
    assert client.get("/quem", headers={"Authorization": f"Bearer {token}"}).json() == {
        "actor": "ana"
    }
    assert client.get("/quem").json() == {"actor": None}
    # fora da request o valor não vaza
    assert current_actor.get() is None
