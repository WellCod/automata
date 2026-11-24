"""Casos da suíte por CSV (ADR-0043): uma linha por caso, ida e volta.

O Excel em português salva com `;` entre colunas, então o separador é detectado no
cabeçalho e as listas dentro da célula usam `|`. Checagem sem coluna própria vai em
`outras`, em JSON, para a exportação não perder nada.
"""

import csv
import io
import json
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.schemas.eval import EvalCaseInput, EvalCheck, TextCheck

MAX_BYTES = 512 * 1024
LIST_SEP = "|"
COLUMNS = (
    "nome",
    "mensagem",
    "contexto",
    "contem",
    "nao_contem",
    "comeca_com",
    "tools",
    "criterio",
    "nota_minima",
    "bloqueio",
    "etapas",
    "outras",
)
REQUIRED = ("nome", "mensagem")
_TEXT_COLUMNS = {"contem": "contains", "nao_contem": "not_contains", "comeca_com": "starts_with"}
_YES = {"sim", "s", "x", "true", "1", "yes"}
# célula que o Excel leria como fórmula; a exportação põe um apóstrofo na frente e a
# importação tira (Fase 49): nome e mensagem podem vir de conversa real
_FORMULA = ("=", "+", "-", "@", "\t", "\r")
MAX_OTHER = 4000
_CHECKS = TypeAdapter(list[EvalCheck])


class CsvError(ValueError):
    """Problema no arquivo inteiro: tamanho, codificação ou cabeçalho."""


@dataclass
class Row:
    """Linha importada: o caso validado ou os erros, com o número da linha no arquivo."""

    line: int
    name: str
    case: EvalCaseInput | None = None
    errors: list[str] = field(default_factory=list)


def _norm(header: str) -> str:
    """Cabeçalho sem acento, em minúscula e com `_`: "Não contém" vira `nao_contem`."""
    text = unicodedata.normalize("NFKD", header.strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.replace(" ", "_").replace("-", "_")


def _decode(raw: bytes) -> str:
    """Texto do arquivo, recusando o que passa do limite; UTF-8 com ou sem BOM, ou cp1252."""
    if len(raw) > MAX_BYTES:
        raise CsvError(f"Arquivo maior que {MAX_BYTES // 1024} KB")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # planilha salva pelo Excel no Windows
        return raw.decode("cp1252")


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(LIST_SEP) if item.strip()]


# nomes das colunas e dos campos das checagens, para a mensagem falar a língua da planilha
_FIELDS = {
    "name": "nome",
    "input": "mensagem",
    "context": "contexto",
    "checks": "checagens",
    "criteria": "criterio",
    "threshold": "nota_minima",
    "tools": "tools",
    "steps": "etapas",
    "rule": "bloqueio",
    "value": "valor",
}


def _message(error: Any) -> str:
    """Erro do pydantic em português, para quem preencheu a planilha."""
    kind = error.get("type", "")
    error_context = error.get("ctx") or {}
    if kind == "string_too_short":
        min_length = error_context.get("min_length", 1)
        if min_length == 1:
            return "não pode ficar vazio"
        return f"precisa de ao menos {min_length} caracteres"
    if kind == "string_too_long":
        return f"passa de {error_context.get('max_length')} caracteres"
    if kind == "too_short":
        return "precisa de ao menos uma checagem" if error["loc"][:1] == ("checks",) else "vazio"
    if kind == "too_long":
        return f"no máximo {error_context.get('max_length')}"
    if kind in ("literal_error", "enum"):
        expected = str(error_context.get("expected", "um valor da lista")).replace(" or ", " ou ")
        return f"valor não aceito (use {expected})"
    if kind in ("greater_than_equal", "less_than_equal"):
        return "fora da faixa aceita"
    return str(error.get("msg", "inválido"))


def _error_text(exc: ValidationError) -> list[str]:
    """Um texto por erro, prefixado pela coluna da planilha quando dá para saber qual."""
    messages = []
    for error in exc.errors():
        parts = [str(part) for part in error["loc"] if not isinstance(part, int)]
        # discriminador da checagem (text, judge...) não é nome de coluna
        named = [_FIELDS[part] for part in parts if part in _FIELDS]
        where = named[-1] if named else ""
        text = _message(error)
        messages.append(f"{where}: {text}" if where else text)
    return messages


def _checks(cells: dict[str, str]) -> tuple[list[Any], list[str]]:
    """Checagens montadas a partir das colunas da linha, ainda sem validar, e os erros."""
    checks: list[Any] = []
    errors: list[str] = []
    for column, kind in _TEXT_COLUMNS.items():
        for value in _split(cells.get(column, "")):
            checks.append(TextCheck(kind=kind, value=value))
    tools = _split(cells.get("tools", ""))
    if tools:
        checks.append({"type": "tools", "tools": tools})
    criteria = cells.get("criterio", "").strip()
    grade = cells.get("nota_minima", "").strip()
    if criteria:
        # com nota mínima o juiz vira numérico; sem ela, binário
        judge: dict[str, Any] = {"type": "judge", "criteria": criteria}
        if grade:
            if not grade.isdigit():
                errors.append("nota_minima: use um número de 1 a 10")
            else:
                judge.update(mode="numeric", threshold=int(grade))
        checks.append(judge)
    elif grade:
        errors.append("nota_minima sem criterio")
    blocked = cells.get("bloqueio", "").strip()
    if blocked:
        # "sim" (e afins) aceita bloqueio por qualquer regra; outro texto é o nome da regra
        checks.append({"type": "blocked", "rule": None if blocked.lower() in _YES else blocked})
    steps = _split(cells.get("etapas", ""))
    if steps:
        checks.append({"type": "steps", "steps": steps})
    other = cells.get("outras", "").strip()
    if len(other) > MAX_OTHER:
        errors.append(f"outras: mais de {MAX_OTHER} caracteres")
    elif other:
        try:
            parsed = json.loads(other)
            if not isinstance(parsed, list):
                raise TypeError
            checks.extend(parsed)
        except json.JSONDecodeError, TypeError, RecursionError:
            errors.append("outras: JSON inválido")
    return checks, errors


def parse(raw: bytes) -> list[Row]:
    """Linhas do CSV, cada uma com o caso validado ou os erros; problema no arquivo levanta."""
    text = _decode(raw)
    header_line = text.split("\n", 1)[0]
    # o Excel em português salva com `;`; o separador que mais aparece no cabeçalho vence
    delimiter = ";" if header_line.count(";") > header_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise CsvError("Arquivo vazio") from exc
    names = [_norm(column) for column in header]
    unknown = [
        original
        for original, normalized in zip(header, names, strict=True)
        if normalized and normalized not in COLUMNS
    ]
    if unknown:
        raise CsvError(f"Colunas desconhecidas: {', '.join(unknown)}")
    missing = [column for column in REQUIRED if column not in names]
    if missing:
        raise CsvError(f"Faltam as colunas: {', '.join(missing)}")
    rows: list[Row] = []
    try:
        for values in reader:
            rows.extend(_row(reader.line_num, values, names))
    except csv.Error as exc:
        # campo acima do limite do módulo csv, aspas sem fechar
        raise CsvError(f"Linha {reader.line_num}: {exc}") from exc
    return rows


def _quoted(value: str) -> bool:
    """Célula escapada pela exportação: apóstrofo antes de fórmula ou de outro apóstrofo."""
    return value.startswith("'") and value[1:2] in (*_FORMULA, "'")


def _unescape(value: str) -> str:
    return value[1:] if _quoted(value) else value


def _escape(value: str) -> str:
    # também o texto que já começa com apóstrofo, para a ida e volta não perder nada
    return f"'{value}" if value.startswith(_FORMULA) or _quoted(value) else value


def _row(line: int, values: list[str], names: list[str]) -> list[Row]:
    """Linha em branco some; as outras viram uma `Row`, com caso só quando não há erro."""
    if not any(value.strip() for value in values):
        return []
    # célula que falta no fim da linha conta como vazia; coluna sem nome é ignorada
    cells = {
        name: _unescape(values[i] if i < len(values) else "")
        for i, name in enumerate(names)
        if name
    }
    row = Row(line=line, name=cells.get("nome", "").strip())
    checks, errors = _checks(cells)
    row.errors.extend(errors)
    context = [
        message.strip() for message in cells.get("contexto", "").splitlines() if message.strip()
    ]
    try:
        parsed_checks = _CHECKS.validate_python(checks)
        row.case = EvalCaseInput(
            name=row.name,
            input=cells.get("mensagem", "").strip(),
            context=context,
            checks=parsed_checks,
        )
    except ValidationError as exc:
        row.errors.extend(_error_text(exc))
    if row.errors:
        row.case = None
    return [row]


def _cells(checks: list[dict[str, Any]]) -> dict[str, str]:
    """Checagens distribuídas pelas colunas da planilha.

    O que a coluna própria não consegue representar sem perda (texto com `|`, regra
    numa etapa, tools sem extras, etapas exclusivas, segundo juiz...) vai em `outras`.
    """
    columns: dict[str, list[str]] = {column: [] for column in COLUMNS}
    other: list[dict[str, Any]] = []
    judge_done = False
    for check in checks:
        kind = check.get("type")
        if kind == "text" and not check.get("step") and check.get("kind") in _TEXT_COLUMNS.values():
            column = next(
                column_name
                for column_name, text_kind in _TEXT_COLUMNS.items()
                if text_kind == check["kind"]
            )
            if LIST_SEP in check["value"]:
                other.append(check)
            else:
                columns[column].append(check["value"])
        elif kind == "tools" and check.get("allow_additional", True) and not columns["tools"]:
            columns["tools"] = list(check["tools"])
        elif kind == "judge" and not judge_done:
            judge_done = True
            columns["criterio"] = [check["criteria"]]
            if check.get("mode") == "numeric":
                columns["nota_minima"] = [str(check.get("threshold", 7))]
        elif kind == "blocked" and not columns["bloqueio"]:
            columns["bloqueio"] = [check.get("rule") or "sim"]
        elif kind == "steps" and not check.get("exclusive") and not columns["etapas"]:
            columns["etapas"] = list(check["steps"])
        else:
            other.append(check)
    cells = {column: f" {LIST_SEP} ".join(values) for column, values in columns.items()}
    cells["outras"] = json.dumps(other, ensure_ascii=False) if other else ""
    return cells


def dump(cases: list[Any]) -> str:
    """Suíte em CSV, com `;` para abrir direto no Excel em português."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for case in cases:
        cells = _cells(list(case.checks))
        cells["nome"] = case.name
        cells["mensagem"] = case.input
        cells["contexto"] = "\n".join(case.context or [])
        writer.writerow([_escape(cells[column]) for column in COLUMNS])
    return buffer.getvalue()
