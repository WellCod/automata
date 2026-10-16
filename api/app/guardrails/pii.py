"""Detecção de dados pessoais brasileiros (ADR-0013).

Os padrões do Agno são dos EUA e não validam nada: qualquer sequência de 11
dígitos viraria CPF. Aqui CPF e CNPJ conferem o dígito verificador e cartão
confere o Luhn, para número de pedido ou protocolo não ser bloqueado.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

PiiType = Literal["cpf", "cnpj", "cartao", "email", "telefone"]
PII_TYPES: tuple[PiiType, ...] = ("cpf", "cnpj", "cartao", "email", "telefone")

_LABEL: dict[PiiType, str] = {
    "cpf": "[CPF removido]",
    "cnpj": "[CNPJ removido]",
    "cartao": "[cartão removido]",
    "email": "[e-mail removido]",
    "telefone": "[telefone removido]",
}


@dataclass(frozen=True)
class Match:
    type: PiiType
    start: int
    end: int


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def cpf_valido(text: str) -> bool:
    d = _digits(text)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(d[i]) * (size + 1 - i) for i in range(size))
        if int(d[size]) != (total * 10 % 11) % 10:
            return False
    return True


def cnpj_valido(text: str) -> bool:
    d = _digits(text)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for size in (12, 13):
        weights = list(range(size - 7, 1, -1)) + list(range(9, 1, -1))
        total = sum(int(d[i]) * weights[i] for i in range(size))
        rest = total % 11
        if int(d[size]) != (0 if rest < 2 else 11 - rest):
            return False
    return True


def luhn_valido(text: str) -> bool:
    d = _digits(text)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Fronteira por não-dígito em vez de \b: "CPF:12345678909" também casa
_PATTERNS: dict[PiiType, tuple[re.Pattern[str], Callable[[str], bool] | None]] = {
    "cnpj": (re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}(?!\d)"), cnpj_valido),
    "cpf": (re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?\d{2}(?!\d)"), cpf_valido),
    "cartao": (re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"), luhn_valido),
    "email": (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), None),
    # celular e fixo com DDD; exige formatação ou +55 para não casar com qualquer número
    "telefone": (
        re.compile(
            r"(?:\+55\s?)?\(\d{2}\)\s?9?\d{4}-?\d{4}"
            r"|\+55\s?\d{2}\s?9?\d{4}-?\d{4}"
            r"|(?<!\d)\d{2}\s9?\d{4}-\d{4}(?!\d)"
        ),
        None,
    ),
}


def find_pii(text: str, types: tuple[PiiType, ...] | list[PiiType] = PII_TYPES) -> list[Match]:
    """Ocorrências sem sobreposição; CNPJ antes de CPF e cartão, que casariam dentro dele."""
    found: list[Match] = []
    taken: list[tuple[int, int]] = []
    for kind, (pattern, valid) in _PATTERNS.items():
        if kind not in types:
            continue
        for m in pattern.finditer(text):
            start, end = m.span()
            if any(start < e and s < end for s, e in taken):
                continue
            if valid is not None and not valid(m.group(0)):
                continue
            found.append(Match(kind, start, end))
            taken.append((start, end))
    return sorted(found, key=lambda m: m.start)


def mask(text: str, matches: list[Match]) -> str:
    out = []
    last = 0
    for m in matches:
        out.append(text[last : m.start])
        out.append(_LABEL[m.type])
        last = m.end
    out.append(text[last:])
    return "".join(out)
