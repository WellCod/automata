"""Evals dos conectores e da reindexação (ADR-0024).

Sem banco e sem rede: rodam em todo PR. Errar o plano reindexa o que não mudou
(e cobra embedding) ou deixa na base o que já saiu da origem; errar o caminho
traz para a base arquivo de fora da pasta configurada.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.knowledge.connector_sync import MAX_FILES, plan, selectable
from app.knowledge.schedule import next_at
from app.knowledge.sources import RemoteFile, _inside


@pytest.mark.parametrize(
    ("path", "folder", "expected"),
    [
        ("docs/a.md", "docs", "a.md"),
        ("docs/sub/a.md", "/docs/", "sub/a.md"),
        ("docs-antigos/a.md", "docs", None),
        ("docs", "docs", None),
        ("a.md", "", "a.md"),
        ("outro/a.md", "docs", None),
    ],
)
def test_so_entra_o_que_esta_dentro_da_pasta(path: str, folder: str, expected: str | None) -> None:
    assert _inside(path, folder) == expected


def _f(path: str, version: str = "v1", size: int = 10) -> RemoteFile:
    return RemoteFile(path=path, version=version, size=size)


def test_plano_pela_versao_remota() -> None:
    igual, mudou, falhou, sumiu = uuid4(), uuid4(), uuid4(), uuid4()
    known = {
        "igual.md": (igual, "v1", "completed"),
        "mudou.md": (mudou, "v1", "completed"),
        # versão igual, mas a última ingestão falhou: baixa de novo
        "falhou.md": (falhou, "v1", "failed"),
        "sumiu.md": (sumiu, "v1", "completed"),
    }
    files = [_f("igual.md"), _f("mudou.md", "v2"), _f("falhou.md"), _f("novo.md")]
    result = plan(known, files)
    assert result.unchanged == 1
    assert [(f.path, cid) for f, cid in result.fetch] == [
        ("mudou.md", mudou),
        ("falhou.md", falhou),
        ("novo.md", None),
    ]
    assert result.gone == [sumiu]


def test_origem_vazia_tira_tudo_da_base() -> None:
    a, b = uuid4(), uuid4()
    result = plan({"a.md": (a, "v1", "completed"), "b.md": (b, "v1", "completed")}, [])
    assert result.fetch == [] and sorted(result.gone) == sorted([a, b])


def test_limites_da_sincronizacao() -> None:
    files = [_f(f"doc{i:04}.md") for i in range(MAX_FILES + 20)]
    files += [_f("foto.png"), _f("grande.pdf", size=50), _f("vazio.md", size=0)]
    chosen, skipped = selectable(files, max_bytes=40)
    assert len(chosen) == MAX_FILES
    # o corte é por nome: a mesma origem dá sempre o mesmo recorte
    assert chosen[0].path == "doc0000.md" and chosen[-1].path == f"doc{MAX_FILES - 1:04}.md"
    assert skipped == 20 + 3


def test_proximo_horario() -> None:
    now = datetime(2026, 10, 21, 12, tzinfo=UTC)
    assert next_at(None, now) is None
    assert next_at(24, now) == now + timedelta(hours=24)


@pytest.mark.parametrize(
    ("path", "extension", "name"),
    [
        ("docs/Troca.MD", "md", "Troca"),
        ("contrato.v2.pdf", "pdf", "contrato.v2"),
        ("LEIAME", "", "LEIAME"),
    ],
)
def test_nome_e_extensao_do_arquivo_remoto(path: str, extension: str, name: str) -> None:
    file = _f(path)
    assert (file.extension, file.name) == (extension, name)
