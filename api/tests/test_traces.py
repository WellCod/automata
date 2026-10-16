"""Árvore de execução: rota com banco falso e captura real de spans em subprocesso."""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.routers.traces import router

_NOW = datetime(2026, 10, 15, tzinfo=UTC)


class FakeDb:
    def __init__(self, user_id: str | None = "dono") -> None:
        self.user_id = user_id

    def get_trace(self, run_id: str | None = None, trace_id: str | None = None) -> Any:
        if run_id != "r1":
            return None
        return SimpleNamespace(
            trace_id="t1",
            name="atendimento.arun",
            status="OK",
            duration_ms=2500,
            start_time=_NOW,
            end_time=_NOW,
            total_spans=2,
            error_count=0,
            run_id="r1",
            session_id="s1",
            user_id=self.user_id,
            agent_id=None,
            team_id="time",
            workflow_id=None,
            created_at=_NOW,
            input="oi",
            output="Maria",
        )

    def get_spans(self, trace_id: str | None = None, **_: Any) -> list[Any]:
        def span(sid: str, parent: str | None, kind: str, name: str) -> Any:
            return SimpleNamespace(
                span_id=sid,
                trace_id="t1",
                parent_span_id=parent,
                name=name,
                span_kind=kind,
                status_code="OK",
                status_message=None,
                start_time=_NOW,
                end_time=_NOW,
                duration_ms=1000,
                attributes={"openinference.span.kind": kind},
                created_at=_NOW,
            )

        return [span("a", None, "TEAM", "atendimento.arun"), span("b", "a", "TOOL", "crm_buscar")]


def _app(db: Any, *, enforce: bool = False, scopes: list[str] | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.agno_db = db
    app.state.enforce_scopes = enforce

    @app.middleware("http")
    async def identidade(request: Request, call_next: Any) -> Any:
        request.state.user_id = "outro"
        request.state.scopes = scopes or ["metrics:read"]
        return await call_next(request)

    return TestClient(app)


def test_arvore_tipada_com_filhos() -> None:
    resp = _app(FakeDb()).get("/api/v1/runs/r1/trace")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    raiz = body["tree"][0]
    assert raiz["type"] == "TEAM"
    assert [s["name"] for s in raiz["spans"]] == ["crm_buscar"]
    assert raiz["spans"][0]["spans"] == []


def test_run_sem_trace_da_404() -> None:
    assert _app(FakeDb()).get("/api/v1/runs/outro/trace").status_code == 404


def test_tracing_desligado_da_404() -> None:
    assert _app(None).get("/api/v1/runs/r1/trace").status_code == 404


def test_trace_de_outro_usuario_so_para_admin() -> None:
    assert _app(FakeDb(), enforce=True).get("/api/v1/runs/r1/trace").status_code == 403
    admin = _app(FakeDb(), enforce=True, scopes=["agent_os:admin"])
    assert admin.get("/api/v1/runs/r1/trace").status_code == 200
    dono = _app(FakeDb(user_id="outro"), enforce=True)
    assert dono.get("/api/v1/runs/r1/trace").status_code == 200


def test_spans_reais_de_time_com_tool_mcp() -> None:
    """Tracing de verdade, em processo próprio: o provider do OpenTelemetry é global."""
    from testcontainers.postgres import PostgresContainer

    api_dir = Path(__file__).resolve().parent.parent
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {**os.environ, "DATABASE_URL": url, "JWT_PRIVATE_KEY": "x", "JWT_PUBLIC_KEY": "x"}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=api_dir,
            env=env,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "tests.trace_scenario", url],
            cwd=api_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
    line = next((x for x in result.stdout.splitlines() if x.startswith("TRACE_JSON=")), None)
    if line is None:
        pytest.fail(f"cenário falhou:\n{result.stdout[-2000:]}\n{result.stderr[-4000:]}")
    payload = json.loads(line.removeprefix("TRACE_JSON="))
    assert payload["status"] == 200, payload

    def flatten(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for n in nodes:
            out += [n, *flatten(n["spans"])]
        return out

    spans = flatten(payload["body"]["tree"])
    assert spans[0]["type"] == "TEAM"
    assert {"AGENT", "TOOL"} <= {s["type"] for s in spans}
    assert any("buscar_cliente" in s["name"] for s in spans)
