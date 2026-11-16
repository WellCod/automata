"""Documento zip com teto no conteúdo descomprimido (SEC-06)."""

import io
import zipfile

import pytest

from app.knowledge.ingest import IngestError, read_documents


def _docx(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buf.getvalue()


def test_docx_que_explode_ao_abrir_e_recusado_antes_do_leitor() -> None:
    # 210 MB de zeros cabem em poucos KB comprimidos
    bomb = _docx({"word/document.xml": b"\0" * (210 * 1024 * 1024)})
    assert len(bomb) < 1024 * 1024
    with pytest.raises(IngestError, match="descomprimido"):
        read_documents("bomba", "docx", bomb, 1000)


def test_docx_que_nao_e_zip_e_recusado() -> None:
    with pytest.raises(IngestError, match="corrompido"):
        read_documents("falso", "docx", b"nao sou zip", 1000)
