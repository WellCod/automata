"""Saída estruturada por JSON Schema (ADR-0027): validação na escrita e conferência da resposta.

O tamanho em bytes não limita o custo de validar: `$ref` em cadeia dentro de `allOf`
dobra o trabalho a cada nível, e um `pattern` com quantificador aninhado é exponencial
no `re`, que segura o GIL (auditoria da Fase 33). Por isso a escrita expande os `$ref`
com orçamento de nós e recusa padrão perigoso, e a suíte confere fora do event loop.
"""

import asyncio
import json
import re
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

MAX_SCHEMA_BYTES = 32 * 1024
# nós do schema com os $ref expandidos: é o que a validação percorre por instância
MAX_EXPANDED_NODES = 2000
MAX_SCHEMA_DEPTH = 32
MAX_PATTERN_CHARS = 200
# resposta maior que isso nem é conferida: falha com o motivo
MAX_VALIDATED_CHARS = 200_000
VALIDATION_TIMEOUT_SECONDS = 5.0

# grupo com quantificador ou alternância dentro, quantificado de novo: (a+)+, (a|aa)*
_NESTED_QUANTIFIER = re.compile(r"\((?:[^()\\]|\\.)*[+*}|](?:[^()\\]|\\.)*\)\s*[+*{]")


class _TooBig(Exception):
    pass


def _pointer(root: Any, ref: str) -> Any:
    node = root
    for raw in ref[2:].split("/") if ref != "#" else []:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            raise _TooBig(f"$ref não encontrado: {ref}")
    return node


def _pattern_problem(pattern: Any) -> str | None:
    if not isinstance(pattern, str):
        return None
    if len(pattern) > MAX_PATTERN_CHARS:
        return f"pattern com mais de {MAX_PATTERN_CHARS} caracteres"
    if _NESTED_QUANTIFIER.search(pattern):
        return f"pattern com quantificador aninhado: {pattern[:60]}"
    return None


def _expansion_problem(schema: dict[str, Any]) -> str | None:
    count = 0

    def visit(node: Any, depth: int, refs: frozenset[str]) -> None:
        nonlocal count
        count += 1
        if count > MAX_EXPANDED_NODES:
            raise _TooBig(f"schema expandido com mais de {MAX_EXPANDED_NODES} nós")
        if depth > MAX_SCHEMA_DEPTH:
            raise _TooBig(f"schema com mais de {MAX_SCHEMA_DEPTH} níveis")
        if isinstance(node, list):
            for item in node:
                visit(item, depth + 1, refs)
            return
        if not isinstance(node, dict):
            return
        if "$dynamicRef" in node or "$recursiveRef" in node:
            raise _TooBig("$dynamicRef não é aceito")
        ref = node.get("$ref")
        if ref is not None:
            if not isinstance(ref, str) or not (ref == "#" or ref.startswith("#/")):
                raise _TooBig(f"$ref só para dentro do schema (#/...): {str(ref)[:60]}")
            if ref in refs:
                raise _TooBig(f"$ref recursivo: {ref}")
            visit(_pointer(schema, ref), depth + 1, refs | {ref})
        for key, value in node.items():
            if key in ("$ref", "$defs", "definitions"):
                # as definições contam onde são usadas, pela expansão do $ref
                continue
            if key == "pattern":
                problem = _pattern_problem(value)
                if problem:
                    raise _TooBig(problem)
            if key == "patternProperties" and isinstance(value, dict):
                for pattern in value:
                    problem = _pattern_problem(pattern)
                    if problem:
                        raise _TooBig(problem)
            visit(value, depth + 1, refs)

    try:
        visit(schema, 0, frozenset())
    except _TooBig as exc:
        return str(exc)
    return None


def schema_problems(schema: dict[str, Any]) -> list[str]:
    """Erros do schema para a escrita; lista vazia quando serve."""
    if len(json.dumps(schema, ensure_ascii=False).encode()) > MAX_SCHEMA_BYTES:
        return [f"schema de saída maior que {MAX_SCHEMA_BYTES // 1024} KB"]
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        return [f"schema de saída inválido: {exc.message}"]
    problem = _expansion_problem(schema)
    if problem:
        return [f"schema de saída: {problem}"]
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
    if len(json.dumps(data, ensure_ascii=False)) > MAX_VALIDATED_CHARS:
        return {"passed": False, "errors": ["resposta grande demais para conferir"]}
    errors = sorted(
        Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path)
    )
    messages = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '(raiz)'}: {e.message}" for e in errors[:5]
    ]
    return {"passed": not errors, "errors": messages}


async def aschema_verdict(schema: dict[str, Any], content: Any) -> dict[str, Any]:
    """Conferência fora do event loop e com prazo: schema gravado antes dos limites
    da escrita ainda pode ser caro, e a suíte roda no processo da API."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(schema_verdict, schema, content), VALIDATION_TIMEOUT_SECONDS
        )
    except TimeoutError:
        seconds = f"{VALIDATION_TIMEOUT_SECONDS:.0f}"
        return {"passed": False, "errors": [f"a conferência do schema passou de {seconds} s"]}
    except Exception as exc:
        # $ref que não resolve, recursão: o caso falha com o motivo em vez de quebrar a suíte
        return {"passed": False, "errors": [f"schema não conferido: {type(exc).__name__}"]}
