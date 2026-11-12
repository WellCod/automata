"""Traces por OTLP (ADR-0043): os mesmos spans que o AgentOS grava no banco, para a
ferramenta de observabilidade da empresa.

O provider do OpenTelemetry é global e é criado pelo AgentOS no construtor. Aqui só
entra mais um processador, uma vez por processo. Sem `OTEL_EXPORT_CONTENT`, o span sai
sem o texto da conversa e sem o id do usuário final.
"""

import hashlib
import logging
import threading
from collections.abc import Mapping, Sequence
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status

from app.settings import Settings

logger = logging.getLogger(__name__)

# prefixos dos atributos com texto da conversa, do prompt ou de quem conversou
CONTENT_PREFIXES = (
    "input.value",
    "input.mime_type",
    "output.value",
    "output.mime_type",
    "llm.input_messages",
    "llm.output_messages",
    "llm.prompts",
    "llm.prompt_template",
    "llm.function_call",
    "tool.parameters",
    "tool_call.function.arguments",
    "message.",
    "retrieval.documents",
    "reranker.",
    "embedding.embeddings",
    "metadata",
    "user.id",
)

_lock = threading.Lock()
_attached = False
_processor: BatchSpanProcessor | None = None


def _is_content(key: str) -> bool:
    return key.startswith(CONTENT_PREFIXES)


def _without_content(attributes: Mapping[str, Any] | None) -> dict[str, Any]:
    kept = {k: v for k, v in (attributes or {}).items() if not _is_content(k)}
    # muita integração usa telefone ou e-mail como sessão: sai em hash, que ainda junta os
    # spans da mesma conversa no fornecedor (Fase 49)
    if isinstance(kept.get("session.id"), str):
        kept["session.id"] = hashlib.sha256(kept["session.id"].encode()).hexdigest()[:16]
    return kept


def _events_without_content(events: Sequence[Event]) -> list[Event]:
    # exceção fica com o tipo; a mensagem pode trazer o texto que falhou
    kept: list[Event] = []
    for event in events:
        attrs = event.attributes or {}
        if event.name == "exception":
            kept.append(
                Event(
                    "exception",
                    {"exception.type": str(attrs.get("exception.type", ""))},
                    event.timestamp,
                )
            )
    return kept


class FilteringExporter(SpanExporter):
    """Troca o recurso pelo da instância e tira o conteúdo antes de exportar."""

    def __init__(self, inner: SpanExporter, resource: Resource, include_content: bool) -> None:
        self._inner = inner
        self._resource = resource
        self._include_content = include_content

    def _rewrite(self, span: ReadableSpan) -> ReadableSpan:
        attributes = dict(span.attributes or {}) if self._include_content else None
        return ReadableSpan(
            name=span.name,
            context=span.context,
            parent=span.parent,
            resource=self._resource,
            attributes=attributes if attributes is not None else _without_content(span.attributes),
            events=list(span.events)
            if self._include_content
            else _events_without_content(span.events),
            links=span.links,
            kind=span.kind,
            # o instrumentador põe str(exceção) na descrição, com o texto que falhou
            status=span.status if self._include_content else Status(span.status.status_code),
            start_time=span.start_time,
            end_time=span.end_time,
            instrumentation_scope=span.instrumentation_scope,
        )

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._inner.export([self._rewrite(s) for s in spans])

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._inner.force_flush(timeout_millis)


def _otlp_exporter() -> SpanExporter:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    # endpoint e cabeçalhos pelas variáveis padrão OTEL_EXPORTER_OTLP_*
    return OTLPSpanExporter()


def attach_otlp(settings: Settings, exporter: SpanExporter | None = None) -> bool:
    """Liga a exportação; devolve se o processador entrou agora."""
    global _attached, _processor
    if not settings.otel_export_enabled:
        return False
    if not settings.tracing_enabled:
        logger.warning("OTEL_EXPORT_ENABLED sem TRACING_ENABLED: não há spans para exportar")
        return False
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        logger.warning("tracing do AgentOS não configurado; exportação OTLP desligada")
        return False
    with _lock:
        if _attached:
            return False
        resource = Resource.create({"service.name": settings.otel_service_name})
        processor = BatchSpanProcessor(
            FilteringExporter(exporter or _otlp_exporter(), resource, settings.otel_export_content)
        )
        provider.add_span_processor(processor)
        _processor = processor
        _attached = True
    logger.info(
        "exportação OTLP ligada",
        extra={"service": settings.otel_service_name, "content": settings.otel_export_content},
    )
    return True


def shutdown_otlp() -> None:
    """Esvazia e desliga o processador; o provider segue gravando no banco."""
    global _attached, _processor
    with _lock:
        if _processor is not None:
            _processor.shutdown()  # type: ignore[no-untyped-call]
        _processor = None
        _attached = False
