"""Traces por OTLP (ADR-0043): o filtro de conteúdo e a ligação uma vez por processo."""

from collections.abc import Generator

import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import telemetry
from app.settings import Settings

ATTRS = {
    "openinference.span.kind": "LLM",
    "llm.model_name": "claude-haiku-4-5",
    "llm.token_count.prompt": 120,
    "llm.token_count.completion": 30,
    "input.value": "meu CPF é 123.456.789-09",
    "output.value": "anotado",
    "llm.input_messages.0.message.content": "meu CPF é 123.456.789-09",
    "llm.output_messages.0.message.content": "anotado",
    "tool.parameters": '{"cpf": "12345678909"}',
    "user.id": "cliente-77",
    "session.id": "s-1",
    "agno.run.id": "r-1",
}


def _export(include_content: bool) -> dict[str, object]:
    sink = InMemorySpanExporter()
    exporter = telemetry.FilteringExporter(
        sink, Resource.create({"service.name": "automata-teste"}), include_content
    )
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("teste")
    with tracer.start_as_current_span("Agent.arun", attributes=ATTRS) as span:
        try:
            raise ValueError("falhou com o CPF 123.456.789-09")
        except ValueError as exc:
            span.record_exception(exc)
    (finished,) = sink.get_finished_spans()
    assert finished.resource.attributes["service.name"] == "automata-teste"
    events = [dict(e.attributes or {}) for e in finished.events]
    return {"attrs": dict(finished.attributes or {}), "events": events}


def test_sem_conteudo_por_padrao() -> None:
    got = _export(include_content=False)
    attrs = got["attrs"]
    assert isinstance(attrs, dict)
    assert attrs["llm.model_name"] == "claude-haiku-4-5"
    assert attrs["llm.token_count.prompt"] == 120
    assert attrs["session.id"] == "s-1"
    assert attrs["agno.run.id"] == "r-1"
    for key in ATTRS:
        if key.startswith(("input.", "output.", "llm.input", "llm.output", "tool.", "user.")):
            assert key not in attrs, key
    assert "123.456.789-09" not in repr(got)
    assert got["events"] == [{"exception.type": "ValueError"}]


def test_conteudo_liberado() -> None:
    got = _export(include_content=True)
    attrs = got["attrs"]
    assert isinstance(attrs, dict)
    assert attrs["input.value"] == "meu CPF é 123.456.789-09"
    assert attrs["user.id"] == "cliente-77"


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch) -> Generator[TracerProvider, None, None]:
    provider = TracerProvider()
    monkeypatch.setattr(telemetry.trace, "get_tracer_provider", lambda: provider)
    monkeypatch.setattr(telemetry, "_attached", False)
    yield provider


def _settings(**kw: object) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://x/y",
        "jwt_private_key": "x",
        "jwt_public_key": "x",
    }
    return Settings(**{**base, **kw})  # type: ignore[arg-type]


def test_desligado_por_padrao(fresh: TracerProvider) -> None:
    assert telemetry.attach_otlp(_settings(), exporter=InMemorySpanExporter()) is False


def test_liga_uma_vez_e_exige_tracing(fresh: TracerProvider) -> None:
    sink = InMemorySpanExporter()
    assert (
        telemetry.attach_otlp(_settings(otel_export_enabled=True, tracing_enabled=False), sink)
        is False
    )
    on = _settings(otel_export_enabled=True, tracing_enabled=True)
    assert telemetry.attach_otlp(on, sink) is True
    assert telemetry.attach_otlp(on, sink) is False
    with fresh.get_tracer("t").start_as_current_span("run"):
        pass
    fresh.force_flush()
    assert [s.name for s in sink.get_finished_spans()] == ["run"]
    assert sink.get_finished_spans()[0].resource.attributes["service.name"] == "automata-api"
