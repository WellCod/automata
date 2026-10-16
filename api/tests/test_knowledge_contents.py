"""Ingestão de conteúdo nas bases: arquivo, URL e texto, estado, remoção e SSRF (ADR-0012)."""

import io
import os
import threading
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from uuid import UUID

import pytest
from agno.knowledge.embedder.base import Embedder
from alembic.config import Config
from docx import Document as DocxDocument
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.knowledge.ingest import count_chunks, fail_stale
from app.knowledge.runtime import vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.settings import get_settings


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    from app.main import create_app

    # embedder local e determinístico: sem chave e sem rede
    monkeypatch.setenv("DEMO_REPLAY", "true")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "127.0.0.1")
    get_settings.cache_clear()
    with TestClient(create_app(auto_provision_dbs=False, enable_auth=False)) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def base_id(client: TestClient) -> Generator[str, None, None]:
    created = client.post(
        "/api/v1/knowledge-bases",
        json={"name": f"RH {os.urandom(3).hex()}", "slug": f"rh_{os.urandom(3).hex()}"},
    )
    assert created.status_code == 201, created.text
    yield created.json()["id"]
    client.delete(f"/api/v1/knowledge-bases/{created.json()['id']}")


def _base(base_id: str) -> KnowledgeBase:
    with Session(get_engine()) as session:
        base = session.get(KnowledgeBase, UUID(base_id))
        assert base is not None
        session.expunge(base)
        return base


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 18 Tf 20 100 Td ({text}) Tj ET".encode()
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 144]/Contents 4 0 R"
        b"/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = io.BytesIO(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj" % i + obj + b"endobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref))
    return out.getvalue()


def _docx(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


@pytest.mark.parametrize(
    ("filename", "data", "termo"),
    [
        ("ferias.md", "# Férias\n\nCada colaborador tem trinta dias de férias.".encode(), "férias"),
        ("reembolso.txt", "Reembolso exige nota fiscal em até cinco dias.".encode(), "nota"),
        ("viagem.docx", _docx("Viagens internacionais pedem aprovação do diretor."), "diretor"),
        ("ponto.pdf", _pdf("Registro de ponto eletronico obrigatorio"), "ponto"),
    ],
    ids=["md", "txt", "docx", "pdf"],
)
def test_upload_indexa_e_fica_buscavel(
    client: TestClient, base_id: str, filename: str, data: bytes, termo: str
) -> None:
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/file", files={"file": (filename, data)}
    )
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "processing"

    # o TestClient roda a background task antes de devolver
    content = client.get(f"/api/v1/knowledge-bases/{base_id}/contents/{resp.json()['id']}").json()
    assert content["status"] == "completed", content["status_message"]
    assert content["chunk_count"] >= 1
    assert content["source"] == filename

    docs = vector_db_for(_base(base_id)).search(termo, limit=1)
    assert docs and termo in docs[0].content.lower()
    assert docs[0].meta_data["content_id"] == content["id"]


def test_texto_e_remocao_apagam_trechos(client: TestClient, base_id: str) -> None:
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/text",
        json={"name": "Benefícios", "text": "Vale-refeição de trinta reais por dia útil."},
    )
    content_id = resp.json()["id"]
    listed = client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json()
    assert [c["id"] for c in listed] == [content_id]
    assert count_chunks(_base(base_id), UUID(content_id)) >= 1

    assert (
        client.delete(f"/api/v1/knowledge-bases/{base_id}/contents/{content_id}").status_code == 204
    )
    assert count_chunks(_base(base_id), UUID(content_id)) == 0
    assert client.get(f"/api/v1/knowledge-bases/{base_id}/contents/{content_id}").status_code == 404


def test_extensao_e_tamanho_recusados(
    client: TestClient, base_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"/api/v1/knowledge-bases/{base_id}/contents/file"
    assert client.post(url, files={"file": ("virus.exe", b"MZ")}).status_code == 415

    monkeypatch.setenv("KNOWLEDGE_MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    big = b"a" * (1024 * 1024 + 1)
    assert client.post(url, files={"file": ("grande.txt", big)}).status_code == 413


def test_conteudo_sem_texto_vira_falha(client: TestClient, base_id: str) -> None:
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/file", files={"file": ("vazio.md", b"   \n")}
    )
    content = client.get(f"/api/v1/knowledge-bases/{base_id}/contents/{resp.json()['id']}").json()
    assert content["status"] == "failed"
    assert "nenhum texto" in content["status_message"]


class _BrokenEmbedder(Embedder):
    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        raise RuntimeError("chave do embedder inválida")


def test_erro_do_embedder_vira_mensagem(
    client: TestClient, base_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.knowledge.runtime.build_embedder", lambda *a: _BrokenEmbedder(dimensions=256)
    )
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/text", json={"name": "x", "text": "texto"}
    )
    content = client.get(f"/api/v1/knowledge-bases/{base_id}/contents/{resp.json()['id']}").json()
    assert content["status"] == "failed"
    assert "chave do embedder inválida" in content["status_message"]


def test_processing_parado_vira_falha(client: TestClient, base_id: str) -> None:
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/text", json={"name": "y", "text": "texto"}
    )
    content_id = UUID(resp.json()["id"])
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(status="processing", updated_at=datetime.now(UTC) - timedelta(hours=1))
        )
        session.commit()

    assert fail_stale() >= 1
    with Session(get_engine()) as session:
        row = session.get(KnowledgeContent, content_id)
        assert row is not None
        assert row.status == "failed"
        assert "reinício" in (row.status_message or "")


def test_remover_base_remove_conteudos(client: TestClient) -> None:
    base = client.post("/api/v1/knowledge-bases", json={"name": "Temp", "slug": "temp"}).json()
    resp = client.post(
        f"/api/v1/knowledge-bases/{base['id']}/contents/text", json={"name": "z", "text": "texto"}
    )
    assert client.delete(f"/api/v1/knowledge-bases/{base['id']}").status_code == 204
    with Session(get_engine()) as session:
        assert session.get(KnowledgeContent, UUID(resp.json()["id"])) is None


# --- URL ---


class _Site(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/manual":
            body = b"<html><script>x()</script><body><h1>Manual</h1><p>Senha expira em 90 dias.</p>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/redireciona":
            self.send_response(302)
            self.send_header("Location", "http://10.0.0.8/segredo")
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(b"\x89PNG")

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def site() -> Generator[str, None, None]:
    server = HTTPServer(("127.0.0.1", 0), _Site)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _add_url(client: TestClient, base_id: str, url: str) -> dict[str, Any]:
    resp = client.post(f"/api/v1/knowledge-bases/{base_id}/contents/url", json={"url": url})
    assert resp.status_code == 202, resp.text
    result: dict[str, Any] = client.get(
        f"/api/v1/knowledge-bases/{base_id}/contents/{resp.json()['id']}"
    ).json()
    return result


def test_url_html_vira_texto_sem_script(client: TestClient, base_id: str, site: str) -> None:
    content = _add_url(client, base_id, f"{site}/manual")
    assert content["status"] == "completed", content["status_message"]
    docs = vector_db_for(_base(base_id)).search("senha expira", limit=1)
    assert "90 dias" in docs[0].content
    assert "x()" not in docs[0].content


def test_redirect_para_rede_interna_e_barrado(client: TestClient, base_id: str, site: str) -> None:
    content = _add_url(client, base_id, f"{site}/redireciona")
    assert content["status"] == "failed"
    assert "10.0.0.8" in content["status_message"] or "http só" in content["status_message"]


def test_tipo_nao_suportado(client: TestClient, base_id: str, site: str) -> None:
    content = _add_url(client, base_id, f"{site}/imagem")
    assert content["status"] == "failed"
    assert "image/png" in content["status_message"]


def test_url_interna_recusada_na_hora(client: TestClient, base_id: str) -> None:
    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/url", json={"url": "http://192.168.0.10/x"}
    )
    assert resp.status_code == 422


# --- busca de teste ---


def test_busca_devolve_trecho_fonte_e_score(client: TestClient, base_id: str) -> None:
    for name, text in [
        ("Férias", "Cada colaborador tem trinta dias de férias por ano."),
        ("Reembolso", "Reembolso de viagem exige nota fiscal em até cinco dias."),
    ]:
        client.post(
            f"/api/v1/knowledge-bases/{base_id}/contents/text", json={"name": name, "text": text}
        )

    resp = client.post(
        f"/api/v1/knowledge-bases/{base_id}/search",
        json={"query": "quantos dias de férias", "max_results": 1},
    )
    assert resp.status_code == 200, resp.text
    [hit] = resp.json()
    assert "férias" in hit["text"]
    assert hit["content_name"] == "Férias"
    assert hit["source"] == "Férias"
    assert 0 <= hit["score"] <= 1


def test_busca_em_base_vazia(client: TestClient, base_id: str) -> None:
    resp = client.post(f"/api/v1/knowledge-bases/{base_id}/search", json={"query": "qualquer"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_busca_com_embedder_quebrado_da_502(
    client: TestClient, base_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/text", json={"name": "a", "text": "texto"}
    )
    monkeypatch.setattr(
        "app.knowledge.runtime.build_embedder", lambda *a: _BrokenEmbedder(dimensions=256)
    )
    resp = client.post(f"/api/v1/knowledge-bases/{base_id}/search", json={"query": "texto"})
    assert resp.status_code == 502
    assert "chave do embedder inválida" in resp.text
