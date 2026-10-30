"""Saída estruturada por JSON Schema (ADR-0027): validação na escrita e conferência da resposta."""

import json
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

MAX_SCHEMA_BYTES = 32 * 1024


def schema_problems(schema: dict[str, Any]) -> list[str]:
    """Erros do schema para a escrita; lista vazia quando serve."""
    if len(json.dumps(schema, ensure_ascii=False).encode()) > MAX_SCHEMA_BYTES:
        return [f"schema de saída maior que {MAX_SCHEMA_BYTES // 1024} KB"]
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"schema de saída inválido: {exc.message}"]
    # provedores com saída estruturada nativa exigem objeto na raiz
    if schema.get("type") != "object":
        return ["schema de saída precisa ter type object na raiz"]
    return []


def as_json(content: Any) -> Any:
    """A resposta como objeto: o Agno já devolve dict com schema, o replay devolve texto."""
    if isinstance(content, dict | list):
        return content
    if isinstance(content, str):
        try:
            return json.loads(content)
        except ValueError:
            return None
    return None


def schema_verdict(schema: dict[str, Any], content: Any) -> dict[str, Any]:
    data = as_json(content)
    if data is None:
        return {"passed": False, "errors": ["a resposta não é JSON"]}
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path)
    )
    messages = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(raiz)'}: {e.message}" for e in errors[:5]
    ]
    return {"passed": not errors, "errors": messages}
