"""Evals da Fase 48 (ADR-0043) pelo caminho de verdade.

- Um run do agente, com o modelo falso, chega por OTLP/HTTP a um coletor local, em
  protobuf, com `service.name` e os ids do run, e sem a mensagem do usuário nem a
  resposta. Com o conteúdo liberado, a mensagem chega.
- Um workflow com checagem de etapas e de texto numa etapa vai para CSV e volta igual
  noutro workflow com as mesmas etapas.
- Uma planilha de 12 linhas com três erros diz exatamente quais, e nada é gravado.
"""

import os
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace import TracerProvider
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

SECRET_MESSAGE = "meu pedido 88812 chegou quebrado"
REPLY = "Sinto muito, vou abrir a troca."


class Collector:
    """Coletor OTLP/HTTP mínimo: guarda o protobuf de cada POST em /v1/traces."""

    def __init__(self) -> None:
        self.requests: list[ExportTraceServiceRequest] = []
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                if self.path == "/v1/traces":
                    msg = ExportTraceServiceRequest()
                    msg.ParseFromString(body)
                    collector.requests.append(msg)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def spans(self) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
        out = []
        for req in self.requests:
            for rs in req.resource_spans:
                resource = {a.key: _value(a.value) for a in rs.resource.attributes}
                for ss in rs.scope_spans:
                    for span in ss.spans:
                        attrs = {a.key: _value(a.value) for a in span.attributes}
                        out.append((resource, attrs, span.name))
        return out

    def close(self) -> None:
        self.server.shutdown()


def _value(v: Any) -> Any:
    kind = v.WhichOneof("value")
    return getattr(v, kind) if kind else None


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app

    model = FixedReplyModel(id="claude-haiku-4-5", reply=REPLY, tokens=50)
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    monkeypatch.setenv("TRACING_ENABLED", "true")
    get_settings.cache_clear()
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _publish(client: TestClient, kind: str, name: str, payload: dict[str, Any]) -> str:
    config_id = str(
        client.post(
            "/api/v1/configs", json={"name": name, "description": f"Use para {name}", "kind": kind}
        ).json()["id"]
    )
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={"name": name, "description": f"Use para {name}", "payload": payload},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _export_run(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, content: bool, agent: str
) -> list[tuple[dict[str, Any], dict[str, Any], str]]:
    from app import telemetry

    collector = Collector()
    try:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", collector.url)
        monkeypatch.setenv("OTEL_EXPORT_ENABLED", "true")
        monkeypatch.setenv("OTEL_EXPORT_CONTENT", str(content).lower())
        monkeypatch.setenv("OTEL_SERVICE_NAME", "automata-eval")
        monkeypatch.setattr(telemetry, "_attached", False)
        get_settings.cache_clear()
        assert telemetry.attach_otlp(get_settings()) is True
        resp = client.post(
            f"/agents/{agent}/runs", data={"message": SECRET_MESSAGE, "stream": "false"}
        )
        assert resp.status_code == 200, resp.text
        provider = trace.get_tracer_provider()
        assert isinstance(provider, TracerProvider)
        provider.force_flush()
        return collector.spans()
    finally:
        telemetry.shutdown_otlp()
        collector.close()
        get_settings.cache_clear()


def test_run_chega_ao_coletor_sem_a_conversa(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = _publish(client, "agent", "atendimento otlp", {"model_id": "claude-haiku-4-5"})
    spans = _export_run(client, monkeypatch, content=False, agent=agent)
    assert spans, "nenhum span chegou ao coletor"
    resources = {r.get("service.name") for r, _, _ in spans}
    assert resources == {"automata-eval"}
    flat = repr([a for _, a, _ in spans])
    assert SECRET_MESSAGE not in flat
    assert REPLY not in flat
    # o modelo falso não é instrumentado; o span do agente leva os ids e nada da conversa
    (agent_span,) = [a for _, a, _ in spans if a.get("agno.agent.id") == agent]
    assert agent_span["agno.run.id"]
    assert agent_span["session.id"]
    assert "input.value" not in agent_span and "output.value" not in agent_span


def test_conteudo_liberado_chega_ao_coletor(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    agent = _publish(client, "agent", "atendimento otlp conteudo", {"model_id": "claude-haiku-4-5"})
    spans = _export_run(client, monkeypatch, content=True, agent=agent)
    assert SECRET_MESSAGE in repr([a for _, a, _ in spans])


def _workflow(client: TestClient, name: str) -> str:
    triagem = _publish(client, "agent", f"{name} triagem", {"model_id": "claude-haiku-4-5"})
    revisao = _publish(client, "agent", f"{name} revisão", {"model_id": "claude-haiku-4-5"})
    steps = [
        {"type": "step", "name": "triagem", "agent_id": triagem},
        {"type": "step", "name": "revisao", "agent_id": revisao},
    ]
    return _publish(client, "workflow", name, {"workflow": {"steps": steps, "history_runs": 2}})


def test_workflow_vai_e_volta_por_csv(client: TestClient) -> None:
    source = _workflow(client, "wf csv origem")
    case = {
        "name": "Troca",
        "input": "Quero trocar o produto",
        "context": ["Comprei semana passada"],
        "checks": [
            {"type": "steps", "steps": ["triagem", "revisao"], "exclusive": True},
            {"type": "text", "kind": "contains", "value": "troca", "step": "triagem"},
            {"type": "text", "kind": "not_empty", "value": ""},
        ],
    }
    created = client.post(f"/api/v1/configs/{source}/eval-cases", json=case)
    assert created.status_code == 201, created.text

    exported = client.get(f"/api/v1/configs/{source}/eval-cases/export").content
    target = _workflow(client, "wf csv destino")
    imported = client.post(
        f"/api/v1/configs/{target}/eval-cases/import",
        files={"file": ("casos.csv", exported, "text/csv")},
    )
    assert imported.status_code == 200, imported.text

    def shape(config: str) -> list[Any]:
        return [
            (c["name"], c["input"], c["context"], sorted(map(str, c["checks"])))
            for c in client.get(f"/api/v1/configs/{config}/eval-cases").json()
        ]

    assert shape(source) == shape(target)


def test_planilha_grande_com_tres_erros(client: TestClient) -> None:
    agent = _publish(client, "agent", "planilha grande", {"model_id": "claude-haiku-4-5"})
    lines = ["nome;mensagem;contem;criterio;nota_minima;bloqueio"]
    for i in range(12):
        lines.append(f"Caso {i};Pergunta {i};resposta {i};;;")
    lines[4] = "Caso 3;;resposta 3;;;"  # sem mensagem
    lines[8] = "Caso 7;Pergunta 7;;Curto;;"  # critério curto demais
    lines[11] = "Caso 10;Pergunta 10;;;;regra_que_nao_existe"  # bloqueio inválido
    raw = ("\r\n".join(lines) + "\r\n").encode("cp1252")
    resp = client.post(
        f"/api/v1/configs/{agent}/eval-cases/import",
        files={"file": ("casos.csv", raw, "text/csv")},
    )
    assert resp.status_code == 422
    bad = {r["line"]: r["errors"] for r in resp.json()["rows"] if r["errors"]}
    assert sorted(bad) == [5, 9, 12]
    assert client.get(f"/api/v1/configs/{agent}/eval-cases").json() == []
