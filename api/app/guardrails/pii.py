"""Detecção de dados pessoais brasileiros (ADR-0013).

Os padrões do Agno são dos EUA e não validam nada: qualquer sequência de 11
dígitos viraria CPF. Aqui CPF e CNPJ conferem o dígito verificador e cartão
confere o Luhn, para número de pedido ou protocolo não ser bloqueado.

Padrões próprios do agente (ADR-0032) viram regex montado aqui, nunca regex livre:
prefixo literal e uma quantidade limitada de dígitos, o que mantém a busca linear.
"""

import bisect
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
    """Padrão próprio do agente: prefixo literal opcional seguido de N a M dígitos."""

    label: str
    prefix: str
    min_digits: int
    max_digits: int


# entre os dígitos vale ponto, hífen, barra ou espaço, um por vez
_SEP = r"[./ -]?"


@lru_cache(maxsize=256)
def compile_custom(pattern: CustomPattern) -> re.Pattern[str]:
    """Regex do padrão próprio; o último dígito fica fora do grupo para não haver separador
    no fim da ocorrência."""
    digits = rf"(?:\d{_SEP}){{{pattern.min_digits - 1},{pattern.max_digits - 1}}}\d(?!\d)"
    if not pattern.prefix:
        return re.compile(rf"(?<!\d){digits}")
    # prefixo fora de outra palavra: "PROT" não casa dentro de "PROTOCOLO123"
    prefix = re.escape(pattern.prefix)
    return re.compile(rf"(?<![A-Za-z0-9]){prefix}[ :#º°-]{{0,2}}{digits}", re.IGNORECASE)


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def cpf_valido(text: str) -> bool:
    """Confere os dois dígitos verificadores; dígitos todos iguais não valem."""
    digits = _digits(text)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    # cada verificador é o módulo 11 dos dígitos anteriores com pesos decrescentes
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        if int(digits[size]) != (total * 10 % 11) % 10:
            return False
    return True


def cnpj_valido(text: str) -> bool:
    """Confere os dois dígitos verificadores; dígitos todos iguais não valem."""
    digits = _digits(text)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    for size in (12, 13):
        # pesos de 5 (ou 6) a 2 e depois de 9 a 2, pela regra da Receita
        weights = list(range(size - 7, 1, -1)) + list(range(9, 1, -1))
        total = sum(int(digits[i]) * weights[i] for i in range(size))
        rest = total % 11
        if int(digits[size]) != (0 if rest < 2 else 11 - rest):
            return False
    return True


def luhn_valido(text: str) -> bool:
    """Número de cartão de 13 a 19 dígitos que passa no algoritmo de Luhn."""
    digits = _digits(text)
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    # da direita para a esquerda, dobra um dígito sim e outro não
    for position, char in enumerate(reversed(digits)):
        digit = int(char)
        if position % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
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
    # intervalos já tomados, sem sobreposição entre si e ordenados pelo início: basta
    # olhar os dois vizinhos. Comparar com todos deixava a busca quadrática no número de
    # ocorrências ("1." repetido dá milhares delas num padrão próprio)
    starts: list[int] = []
    ends: list[int] = []

    def take(kind: str, regex_match: re.Match[str], label: str | None = None) -> None:
        """Guarda a ocorrência se ela não se sobrepõe a nenhuma já guardada."""
        start, end = regex_match.span()
        insert_at = bisect.bisect_right(starts, start)
        # o vizinho da esquerda termina depois do início desta
        if insert_at > 0 and ends[insert_at - 1] > start:
            return
        # o vizinho da direita começa antes do fim desta
        if insert_at < len(starts) and starts[insert_at] < end:
            return
        found.append(Match(kind, start, end, label))
        starts.insert(insert_at, start)
        ends.insert(insert_at, end)

    for kind, (pattern, valid) in _PATTERNS.items():
        if kind not in types:
            continue
        for regex_match in pattern.finditer(text):
            if valid is None or valid(regex_match.group(0)):
                take(kind, regex_match)
    for custom_pattern in custom:
        for regex_match in compile_custom(custom_pattern).finditer(text):
            take(f"custom:{custom_pattern.label}", regex_match, custom_pattern.label)
    return sorted(found, key=lambda pii_match: pii_match.start)


def mask(text: str, matches: list[Match]) -> str:
    """Troca cada ocorrência pelo rótulo; `matches` precisa vir ordenado e sem sobreposição."""
    parts = []
    copied_until = 0
    for match in matches:
        parts.append(text[copied_until : match.start])
        parts.append(f"[{match.label} removido]" if match.label else _LABEL[match.type])
        copied_until = match.end
    parts.append(text[copied_until:])
    return "".join(parts)
