"""Filtro de arquivos por padrão de nome nos conectores (ADR-0039).

`**/` é qualquer quantidade de pastas (inclusive nenhuma), `**` qualquer coisa, `*`
qualquer coisa dentro de uma pasta e `?` um caractere. Comparado com o caminho relativo
à pasta do conector, sem diferenciar maiúsculas.

O casamento é por autômato, sem regex: cada caractere do caminho visita no máximo
todos os estados do padrão uma vez. O `re` com vários `[^/]*` tinha backtracking
polinomial, e um nome longo e repetitivo na origem travava a API (Fase 43).
"""

from functools import lru_cache

MAX_PATTERNS = 10
MAX_PATTERN_CHARS = 200
MAX_DOUBLE_STARS = 3

# tipos de token
_LIT, _ANY_CHAR, _STAR, _DSTAR, _DIRS = range(5)


def pattern_problem(pattern: str) -> str | None:
    if not pattern.strip():
        return "padrão vazio"
    if len(pattern) > MAX_PATTERN_CHARS:
        return f"padrão com mais de {MAX_PATTERN_CHARS} caracteres"
    if pattern.count("**") > MAX_DOUBLE_STARS:
        return f"no máximo {MAX_DOUBLE_STARS} ** por padrão"
    return None


@lru_cache(maxsize=512)
def tokens(pattern: str) -> tuple[tuple[int, str], ...]:
    out: list[tuple[int, str]] = []
    text = pattern.strip().strip("/").lower()
    i = 0
    while i < len(text):
        if text.startswith("**/", i):
            out.append((_DIRS, ""))
            i += 3
        elif text.startswith("**", i):
            out.append((_DSTAR, ""))
            i += 2
        elif text[i] == "*":
            # `**` vizinhos ou `*` repetidos casam o mesmo: um token só
            if not out or out[-1][0] != _STAR:
                out.append((_STAR, ""))
            i += 1
        elif text[i] == "?":
            out.append((_ANY_CHAR, ""))
            i += 1
        else:
            out.append((_LIT, text[i]))
            i += 1
    return tuple(out)


def _closure(
    toks: tuple[tuple[int, str], ...], states: set[tuple[int, bool]]
) -> set[tuple[int, bool]]:
    # (índice do token, dentro de um `**/` que ainda precisa terminar em "/")
    stack = list(states)
    seen = set(states)
    while stack:
        i, inside = stack.pop()
        if inside or i >= len(toks):
            continue
        kind = toks[i][0]
        nxt: list[tuple[int, bool]] = []
        if kind in (_STAR, _DSTAR, _DIRS):
            nxt.append((i + 1, False))
        for state in nxt:
            if state not in seen:
                seen.add(state)
                stack.append(state)
    return seen


def match(pattern: str, path: str) -> bool:
    toks = tokens(pattern)
    current = _closure(toks, {(0, False)})
    for ch in path.strip("/").lower():
        step: set[tuple[int, bool]] = set()
        for i, inside in current:
            if i >= len(toks):
                continue
            kind, lit = toks[i]
            if kind == _DIRS:
                # dentro de `**/`: consome até um "/", que fecha uma pasta
                step.add((i, True))
                if ch == "/":
                    step.add((i, False))
                    step.add((i + 1, False))
            elif inside:
                continue
            elif kind == _DSTAR:
                step.add((i, False))
            elif kind == _STAR:
                if ch != "/":
                    step.add((i, False))
            elif kind == _ANY_CHAR:
                if ch != "/":
                    step.add((i + 1, False))
            elif ch == lit:
                step.add((i + 1, False))
        if not step:
            return False
        current = _closure(toks, step)
    return (len(toks), False) in current


def allowed(path: str, include: list[str], exclude: list[str]) -> bool:
    """Sem `include` entra tudo; `exclude` vence `include`."""
    if any(match(p, path) for p in exclude):
        return False
    return not include or any(match(p, path) for p in include)
