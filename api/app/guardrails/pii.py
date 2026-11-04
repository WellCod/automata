"""Detecção de dados pessoais brasileiros (ADR-0013).

Os padrões do Agno são dos EUA e não validam nada: qualquer sequência de 11
dígitos viraria CPF. Aqui CPF e CNPJ conferem o dígito verificador e cartão
confere o Luhn, para número de pedido ou protocolo não ser bloqueado.

Padrões próprios do agente (ADR-0032) viram regex montado aqui, nunca regex livre:
prefixo literal e uma quantidade limitada de dígitos, o que mantém a busca linear.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

PiiType = Literal["cpf", "cnpj", "cartao", "email", "telefone"]
PII_TYPES: tuple[PiiType, ...] = ("cpf", "cnpj", "cartao", "email", "telefone")
# acima disso o guardrail barra a mensagem sem varrer (cerca de 0,1 s no teto)
PII_SCAN_MAX_CHARS = 100_000

_LABEL: dict[str, str] = {
    "cpf": "[CPF removido]",
    "cnpj": "[CNPJ removido]",
    "cartao": "[cartão removido]",
    "email": "[e-mail removido]",
    "telefone": "[telefone removido]",
}


@dataclass(frozen=True)
class Match:
    # um dos PII_TYPES ou "custom:<rótulo>"
    type: str
    start: int
    end: int
    label: str | None = None


@dataclass(frozen=True)
class CustomPattern:
    label: str
    prefix: str
    min_digits: int
    max_digits: int


# entre os dígitos vale ponto, hífen, barra ou espaço, um por vez
_SEP = r"[./ -]?"


@lru_cache(maxsize=256)
def compile_custom(pattern: CustomPattern) -> re.Pattern[str]:
    digits = rf"(?:\d{_SEP}){{{pattern.min_digits - 1},{pattern.max_digits - 1}}}\d(?!\d)"
    if not pattern.prefix:
        return re.compile(rf"(?<!\d){digits}")
    # prefixo fora de outra palavra: "PROT" não casa dentro de "PROTOCOLO123"
    prefix = re.escape(pattern.prefix)
    return re.compile(rf"(?<![A-Za-z0-9]){prefix}[ :#º°-]{{0,2}}{digits}", re.IGNORECASE)


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
    # limites do RFC 5321 (64 antes do @, rótulo de até 63): sem eles a busca volta
    # sobre a sequência inteira a cada posição e fica quadrática no tamanho do texto
    "email": (
        re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63}){1,8}"),
        None,
    ),
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


def find_pii(
    text: str,
    types: tuple[PiiType, ...] | list[PiiType] = PII_TYPES,
    custom: tuple[CustomPattern, ...] | list[CustomPattern] = (),
) -> list[Match]:
    """Ocorrências sem sobreposição; CNPJ antes de CPF e cartão, que casariam dentro dele,
    e os padrões próprios por último, para não esconder um CPF com o rótulo de outro."""
    found: list[Match] = []
    taken: list[tuple[int, int]] = []

    def take(kind: str, m: re.Match[str], label: str | None = None) -> None:
        start, end = m.span()
        if any(start < e and s < end for s, e in taken):
            return
        found.append(Match(kind, start, end, label))
        taken.append((start, end))

    for kind, (pattern, valid) in _PATTERNS.items():
        if kind not in types:
            continue
        for m in pattern.finditer(text):
            if valid is None or valid(m.group(0)):
                take(kind, m)
    for item in custom:
        for m in compile_custom(item).finditer(text):
            take(f"custom:{item.label}", m, item.label)
    return sorted(found, key=lambda m: m.start)


def mask(text: str, matches: list[Match]) -> str:
    out = []
    last = 0
    for m in matches:
        out.append(text[last : m.start])
        out.append(f"[{m.label} removido]" if m.label else _LABEL[m.type])
        last = m.end
    out.append(text[last:])
    return "".join(out)
