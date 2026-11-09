"""Filtro de arquivos por padrão de nome nos conectores (ADR-0039)."""

import time

import pytest
from pydantic import ValidationError

from app.knowledge.connector_sync import selectable
from app.knowledge.path_filter import allowed
from app.knowledge.sources import RemoteFile
from app.schemas.knowledge_connector import SETTINGS_BY_KIND, GitHubSettings


@pytest.mark.parametrize(
    ("path", "include", "exclude", "expected"),
    [
        ("politicas/troca.md", ["politicas/**/*.md"], [], True),
        ("politicas/2026/troca.md", ["politicas/**/*.md"], [], True),
        ("CHANGELOG.md", ["politicas/**/*.md"], [], False),
        ("politicas/troca.pdf", ["politicas/**/*.md"], [], False),
        ("README.md", [], [], True),  # sem include entra tudo
        ("rascunhos/novo.md", [], ["rascunhos/**"], False),
        ("politicas/rascunho.md", ["politicas/*.md"], ["**/rascunho*"], False),  # exclude vence
        ("Politicas/Troca.MD", ["politicas/*.md"], [], True),  # sem diferenciar maiúsculas
        ("politicas/sub/troca.md", ["politicas/*.md"], [], False),  # * não atravessa pasta
        ("a/b/c.txt", ["a/?/c.txt"], [], True),
        ("politicas/troca[1].md", ["politicas/troca[1].md"], [], True),  # colchete é literal
    ],
)
def test_glob(path: str, include: list[str], exclude: list[str], expected: bool) -> None:
    assert allowed(path, include, exclude) is expected


def test_glob_hostil_fica_linear() -> None:
    path = "a/" * 500 + "b"
    started = time.perf_counter()
    allowed(path, ["**/**/**/x"], [])
    assert time.perf_counter() - started < 1


@pytest.mark.parametrize(
    "patterns",
    [["**/**/**/**/x"], ["x" * 201], [f"p{i}" for i in range(11)]],
)
def test_padrao_fora_da_regra_e_recusado(patterns: list[str]) -> None:
    with pytest.raises(ValidationError):
        GitHubSettings(repo="org/repo", include=patterns)


def test_todo_tipo_de_conector_aceita_o_filtro() -> None:
    for model in SETTINGS_BY_KIND.values():
        assert {"include", "exclude"} <= set(model.model_fields)


def test_arquivo_fora_do_filtro_some_sem_contar_como_pulado() -> None:
    files = [
        RemoteFile(path="politicas/troca.md", version="1", size=10),
        RemoteFile(path="CHANGELOG.md", version="1", size=10),
        RemoteFile(path="politicas/foto.png", version="1", size=10),
    ]
    chosen, skipped = selectable(files, 1000, {"include": ["politicas/**"]})
    assert [f.path for f in chosen] == ["politicas/troca.md"]
    # a foto passou no filtro e ficou de fora pela extensão; o CHANGELOG nem conta
    assert skipped == 1


def test_muitos_asteriscos_nao_tem_backtracking() -> None:
    """Fase 43: o regex com vários `[^/]*` levava segundos com 22 caracteres."""
    started = time.perf_counter()
    assert not allowed("a" * 200, ["*a" * 13 + "*b"], [])
    assert allowed("_" * 1000 + ".pdf", ["*_*_*_*_*_*_*_*_*_*.pdf"], [])
    assert time.perf_counter() - started < 0.5
