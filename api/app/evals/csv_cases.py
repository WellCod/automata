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
    line: int
    name: str
    case: EvalCaseInput | None = None
    errors: list[str] = field(default_factory=list)


def _norm(header: str) -> str:
    text = unicodedata.normalize("NFKD", header.strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.replace(" ", "_").replace("-", "_")


def _decode(raw: bytes) -> str:
    if len(raw) > MAX_BYTES:
        raise CsvError(f"Arquivo maior que {MAX_BYTES // 1024} KB")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # planilha salva pelo Excel no Windows
        return raw.decode("cp1252")


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split(LIST_SEP) if v.strip()]


def _error_text(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        where = ".".join(str(p) for p in err["loc"] if not isinstance(p, int))
        out.append(f"{where}: {err['msg']}" if where else str(err["msg"]))
    return out


def _checks(cells: dict[str, str]) -> tuple[list[Any], list[str]]:
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
        except (json.JSONDecodeError, TypeError, RecursionError):
            errors.append("outras: JSON inválido")
    return checks, errors


def parse(raw: bytes) -> list[Row]:
    text = _decode(raw)
    first = text.split("\n", 1)[0]
    delimiter = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    try:
        header = next(reader)
    except StopIteration as exc:
        raise CsvError("Arquivo vazio") from exc
    names = [_norm(h) for h in header]
    unknown = [h for h, n in zip(header, names, strict=True) if n and n not in COLUMNS]
    if unknown:
        raise CsvError(f"Colunas desconhecidas: {', '.join(unknown)}")
    missing = [c for c in REQUIRED if c not in names]
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
    return value.startswith("'") and value[1:2] in (*_FORMULA, "'")


def _unescape(value: str) -> str:
    return value[1:] if _quoted(value) else value


def _escape(value: str) -> str:
    # também o texto que já começa com apóstrofo, para a ida e volta não perder nada
    return f"'{value}" if value.startswith(_FORMULA) or _quoted(value) else value


def _row(line: int, values: list[str], names: list[str]) -> list[Row]:
    if not any(v.strip() for v in values):
        return []
    cells = {n: _unescape(values[i] if i < len(values) else "") for i, n in enumerate(names) if n}
    row = Row(line=line, name=cells.get("nome", "").strip())
    checks, errors = _checks(cells)
    row.errors.extend(errors)
    context = [t.strip() for t in cells.get("contexto", "").splitlines() if t.strip()]
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
    cols: dict[str, list[str]] = {c: [] for c in COLUMNS}
    other: list[dict[str, Any]] = []
    judge_done = False
    for check in checks:
        kind = check.get("type")
        if kind == "text" and not check.get("step") and check.get("kind") in _TEXT_COLUMNS.values():
            column = next(c for c, k in _TEXT_COLUMNS.items() if k == check["kind"])
            if LIST_SEP in check["value"]:
                other.append(check)
            else:
                cols[column].append(check["value"])
        elif kind == "tools" and check.get("allow_additional", True) and not cols["tools"]:
            cols["tools"] = list(check["tools"])
        elif kind == "judge" and not judge_done:
            judge_done = True
            cols["criterio"] = [check["criteria"]]
            if check.get("mode") == "numeric":
                cols["nota_minima"] = [str(check.get("threshold", 7))]
        elif kind == "blocked" and not cols["bloqueio"]:
            cols["bloqueio"] = [check.get("rule") or "sim"]
        elif kind == "steps" and not check.get("exclusive") and not cols["etapas"]:
            cols["etapas"] = list(check["steps"])
        else:
            other.append(check)
    out = {c: f" {LIST_SEP} ".join(v) for c, v in cols.items()}
    out["outras"] = json.dumps(other, ensure_ascii=False) if other else ""
    return out


def dump(cases: list[Any]) -> str:
    """Suíte em CSV, com `;` para abrir direto no Excel em português."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow(COLUMNS)
    for case in cases:
        cells = _cells(list(case.checks))
        cells["nome"] = case.name
        cells["mensagem"] = case.input
        cells["contexto"] = "\n".join(case.context or [])
        writer.writerow([_escape(cells[c]) for c in COLUMNS])
    return buf.getvalue()
