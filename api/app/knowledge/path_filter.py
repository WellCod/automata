"""Filtro de arquivos por padrão de nome nos conectores (ADR-0039).

Glob traduzido para regex por nós, sem regex livre de quem configura: `**/` é qualquer
quantidade de pastas (inclusive nenhuma), `**` qualquer coisa, `*` qualquer coisa
dentro de uma pasta e `?` um caractere. Comparado com o caminho relativo à pasta do
conector, sem diferenciar maiúsculas.
"""

import re
from functools import lru_cache

MAX_PATTERNS = 10
MAX_PATTERN_CHARS = 200
# cada `**` vira um `.*`: o limite segura o backtracking num caminho de até 1024
MAX_DOUBLE_STARS = 3


def pattern_problem(pattern: str) -> str | None:
    if not pattern.strip():
        return "padrão vazio"
    if len(pattern) > MAX_PATTERN_CHARS:
        return f"padrão com mais de {MAX_PATTERN_CHARS} caracteres"
    if pattern.count("**") > MAX_DOUBLE_STARS:
        return f"no máximo {MAX_DOUBLE_STARS} ** por padrão"
    return None


@lru_cache(maxsize=512)
def compile_glob(pattern: str) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    text = pattern.strip().strip("/")
    while i < len(text):
        if text.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif text.startswith("**", i):
            out.append(".*")
            i += 2
        elif text[i] == "*":
            out.append("[^/]*")
            i += 1
        elif text[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(text[i]))
            i += 1
    return re.compile("".join(out), re.IGNORECASE)


def allowed(path: str, include: list[str], exclude: list[str]) -> bool:
    """Sem `include` entra tudo; `exclude` vence `include`."""
    target = path.strip("/")
    if any(compile_glob(p).fullmatch(target) for p in exclude):
        return False
    return not include or any(compile_glob(p).fullmatch(target) for p in include)
