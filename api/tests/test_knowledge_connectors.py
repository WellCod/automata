"""Conectores de conhecimento (ADR-0024): cadastro, teste e sincronização pela versão remota."""

import hashlib
import json
import os
import threading
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import UUID

import httpx
import pytest
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.knowledge.sources import RemoteFile, S3Source, SharePointSource
from app.schemas.knowledge_connector import S3Settings, SharePointSettings
from app.settings import get_settings


class FakeGitHub:
    """API do GitHub em 127.0.0.1: árvore do branch e conteúdo bruto, com o token conferido."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        # página servida em /pagina, para a reindexação de URL
        self.page = ""
        self.auth: list[str | None] = []
        self.downloads: list[str] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                fake.auth.append(self.headers.get("Authorization"))
                url = urlsplit(self.path)
                if url.path == "/pagina":
                    self._send(200, fake.page.encode(), "text/plain")
                    return
                if url.path == "/repos/acme/docs/git/trees/main":
                    tree = [
                        {
                            "path": p,
                            "type": "blob",
                            "sha": hashlib.sha1(c.encode()).hexdigest(),
                            "size": len(c.encode()),
                        }
                        for p, c in fake.files.items()
                    ]
                    self._send(200, json.dumps({"tree": tree, "truncated": False}).encode())
                    return
                prefix = "/repos/acme/docs/contents/"
                if url.path.startswith(prefix):
                    path = unquote(url.path[len(prefix) :])
                    fake.downloads.append(path)
                    if path in fake.files:
                        self._send(200, fake.files[path].encode())
                        return
                self._send(404, b"{}")

            def _send(self, status: int, body: bytes, ctype: str = "application/json") -> None:
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture(scope="module")
def github() -> Generator[FakeGitHub, None, None]:
    fake = FakeGitHub()
    yield fake
    fake.server.shutdown()


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        env = {
            "DATABASE_URL": url,
            "MCP_SECRETS_KEY": Fernet.generate_key().decode(),
            "MCP_ALLOWED_HOSTS": "127.0.0.1",
            # embedder local e determinístico: sem chave e sem rede
            "DEMO_REPLAY": "true",
        }
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


@pytest.fixture
def client(db_url: str) -> Generator[TestClient, None, None]:
    from app.main import create_app

    with TestClient(create_app(auto_provision_dbs=False, enable_auth=False)) as c:
        yield c


@pytest.fixture
def base_id(client: TestClient) -> str:
    created = client.post(
        "/api/v1/knowledge-bases",
        json={"name": f"Docs {os.urandom(3).hex()}", "slug": f"docs_{os.urandom(3).hex()}"},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def _chunks(base_id: str) -> int:
    from app.db import get_engine
    from app.knowledge.runtime import vector_db_for
    from app.models.knowledge_base import KnowledgeBase

    with Session(get_engine()) as session:
        base = session.get(KnowledgeBase, UUID(base_id))
        assert base is not None
        vector_db = vector_db_for(base)
        if not vector_db.table_exists():
            return 0
        return int(session.scalar(select(func.count()).select_from(vector_db.table)) or 0)


def _embedding_tokens(base_id: str) -> int:
    from app.db import get_engine
    from app.models.embedding_usage import EmbeddingUsage

    with Session(get_engine()) as session:
        total = session.scalar(
            select(func.coalesce(func.sum(EmbeddingUsage.tokens), 0)).where(
                EmbeddingUsage.base_id == UUID(base_id)
            )
        )
        return int(total or 0)


def test_github_sincroniza_pela_versao_remota(
    client: TestClient, base_id: str, github: FakeGitHub
) -> None:
    github.files = {
        "docs/troca.md": "# Troca\n\nO prazo de troca é de 30 dias corridos.",
        "docs/frete.txt": "Frete grátis acima de R$ 200.",
        "docs/logo.png": "binário",
        "outro/fora.md": "fora da pasta configurada",
    }
    base = f"/api/v1/knowledge-bases/{base_id}/connectors"
    created = client.post(
        base,
        json={
            "kind": "github",
            "name": "Documentação",
            "settings": {"repo": "acme/docs", "path": "docs", "api_url": github.url},
            "secret": {"token": "ghp_segredo"},
        },
    )
    assert created.status_code == 201, created.text
    connector = created.json()
    assert connector["has_secret"] is True
    assert "ghp_segredo" not in json.dumps(client.get(base).json())

    tested = client.post(f"{base}/{connector['id']}/test").json()
    assert tested["ok"] is True and tested["files"] == 2
    assert sorted(tested["sample"]) == ["frete.txt", "troca.md"]
    assert github.auth[-1] == "Bearer ghp_segredo"

    assert client.post(f"{base}/{connector['id']}/sync").status_code == 202
    synced = client.get(base).json()[0]
    assert synced["last_status"] == "ok", synced
    assert synced["last_summary"]["added"] == 2 and synced["last_summary"]["skipped"] == 1
    assert synced["content_count"] == 2
    contents = client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json()
    assert {c["external_path"] for c in contents} == {"troca.md", "frete.txt"}
    assert all(c["source_type"] == "connector" and c["status"] == "completed" for c in contents)
    first_chunks = _chunks(base_id)
    assert first_chunks >= 2

    # nada mudou: não baixa nem cobra embedding de novo
    github.downloads.clear()
    tokens = _embedding_tokens(base_id)
    client.post(f"{base}/{connector['id']}/sync")
    again = client.get(base).json()[0]["last_summary"]
    assert again["unchanged"] == 2 and again["added"] == again["updated"] == 0
    assert github.downloads == []
    assert _embedding_tokens(base_id) == tokens

    # um muda, um some, um aparece
    github.files["docs/troca.md"] = "# Troca\n\nO prazo de troca passou a ser de 15 dias."
    del github.files["docs/frete.txt"]
    github.files["docs/garantia.md"] = "Garantia de 90 dias."
    client.post(f"{base}/{connector['id']}/sync")
    changed = client.get(base).json()[0]["last_summary"]
    assert (changed["updated"], changed["removed"], changed["added"]) == (1, 1, 1)
    contents = client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json()
    assert {c["external_path"] for c in contents} == {"troca.md", "garantia.md"}
    # reindexar não duplica: o trecho antigo de troca.md saiu
    assert _chunks(base_id) == sum(c["chunk_count"] for c in contents)
    found = client.post(
        f"/api/v1/knowledge-bases/{base_id}/search", json={"query": "prazo de troca"}
    ).json()
    texts = " ".join(hit["text"] for hit in found)
    assert "15 dias" in texts and "30 dias" not in texts

    assert client.delete(f"{base}/{connector['id']}").status_code == 204
    assert client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json() == []
    assert _chunks(base_id) == 0


def test_reprocessa_arquivo_do_conector_pela_listagem(
    client: TestClient, base_id: str, github: FakeGitHub
) -> None:
    github.files = {
        "docs/manual.md": "# Troca\nTrinta dias.\n\n# Frete\nGrátis acima de R$ 200.",
        "docs/sumiu.md": "Vai sair da origem.",
    }
    base = f"/api/v1/knowledge-bases/{base_id}/connectors"
    connector = client.post(
        base,
        json={
            "kind": "github",
            "name": "Manual",
            "settings": {"repo": "acme/docs", "path": "docs", "api_url": github.url},
            "secret": {"token": "ghp_segredo"},
        },
    ).json()
    client.post(f"{base}/{connector['id']}/sync")
    assert _chunks(base_id) == 2
    info = client.get(f"/api/v1/knowledge-bases/{base_id}").json()
    resp = client.put(
        f"/api/v1/knowledge-bases/{base_id}",
        json={
            "name": info["name"],
            "chunk_size": info["chunk_size"],
            "chunking": {"strategy": "headings", "heading_level": 1},
        },
    )
    assert resp.status_code == 200, resp.text
    del github.files["docs/sumiu.md"]
    github.downloads.clear()

    result = client.post(f"/api/v1/knowledge-bases/{base_id}/reprocess").json()
    assert result["queued"] == 2 and result["needs_upload"] == []
    contents = {
        c["external_path"]: c
        for c in client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json()
    }
    assert contents["manual.md"]["status"] == "completed"
    assert contents["manual.md"]["chunk_count"] == 2
    # o reprocessamento não sincroniza: o que sumiu da origem vira falha com o motivo
    assert contents["sumiu.md"]["status"] == "failed"
    assert "origem" in contents["sumiu.md"]["status_message"]
    assert len(github.downloads) == 1


def test_conector_invalido_e_recusado(client: TestClient, base_id: str) -> None:
    base = f"/api/v1/knowledge-bases/{base_id}/connectors"
    sharepoint = {
        "hostname": "acme.sharepoint.com",
        "site_path": "/sites/atendimento",
        "tenant_id": "t",
        "client_id": "c",
    }
    cases: list[dict[str, Any]] = [
        # SharePoint sem client secret
        {"kind": "sharepoint", "name": "x", "settings": sharepoint},
        # GitHub Enterprise apontando para a rede interna
        {
            "kind": "github",
            "name": "x",
            "settings": {"repo": "acme/docs", "api_url": "https://10.0.0.5"},
        },
        {"kind": "github", "name": "x", "settings": {"repo": "sem-barra"}},
        {"kind": "s3", "name": "x", "settings": {"bucket": "b"}},
        {
            "kind": "s3",
            "name": "x",
            "settings": {"bucket": "docs-bucket"},
            "secret": {"senha": "x"},
        },
    ]
    for body in cases:
        resp = client.post(base, json=body)
        assert resp.status_code == 422, (body, resp.text)


def test_s3_lista_so_o_prefixo_e_baixa_pela_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {}

    class Body:
        def read(self, amount: int = -1) -> bytes:
            return b"conteudo"

    class Paginator:
        def paginate(self, **kwargs: Any) -> list[dict[str, Any]]:
            calls["paginate"] = kwargs
            return [
                {
                    "Contents": [
                        {"Key": "contratos/", "ETag": '"0"', "Size": 0},
                        {"Key": "contratos/a.pdf", "ETag": '"e1"', "Size": 10},
                        {"Key": "contratos/2026/b.md", "ETag": '"e2"', "Size": 5},
                    ]
                }
            ]

    class Client:
        def get_paginator(self, name: str) -> Paginator:
            return Paginator()

        def get_object(self, **kwargs: Any) -> dict[str, Any]:
            calls["get"] = kwargs
            return {"Body": Body()}

    import boto3

    def fake_client(service: str, **kwargs: Any) -> Client:
        calls["client"] = kwargs
        return Client()

    monkeypatch.setattr(boto3, "client", fake_client)
    source = S3Source(
        S3Settings(bucket="acme-docs", region="sa-east-1", prefix="contratos"),
        {"access_key_id": "AKIA", "secret_access_key": "s"},
    )
    files = source.list_files()
    assert [(f.path, f.version) for f in files] == [("a.pdf", "e1"), ("2026/b.md", "e2")]
    assert calls["paginate"] == {"Bucket": "acme-docs", "Prefix": "contratos/"}
    assert calls["client"]["aws_access_key_id"] == "AKIA"
    assert source.download(files[1]) == b"conteudo"
    assert calls["get"] == {"Bucket": "acme-docs", "Key": "contratos/2026/b.md"}


def test_sharepoint_entra_com_client_credentials_e_percorre_as_pastas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.knowledge.sources as sources

    # a URL assinada é de host público; aqui não há DNS para conferir
    checked: list[str] = []
    monkeypatch.setattr(sources, "check_url", checked.append)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.method} {request.url}")
        url = str(request.url)
        if url.startswith("https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token"):
            assert b"client_secret=segredo" in request.content
            return httpx.Response(200, json={"access_token": "tok"})
        assert request.headers.get("Authorization") == "Bearer tok" or "download" in url
        if url.endswith("/sites/acme.sharepoint.com:/sites/atendimento"):
            return httpx.Response(200, json={"id": "site-1"})
        if url.endswith("/sites/site-1/drive/root:/Procedimentos:/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {"name": "Sub", "folder": {}},
                        {
                            "name": "troca.docx",
                            "file": {},
                            "eTag": "v1",
                            "size": 7,
                            "@microsoft.graph.downloadUrl": "https://acme.sharepoint.com/download/1",
                        },
                    ]
                },
            )
        if url.endswith("/sites/site-1/drive/root:/Procedimentos/Sub:/children"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "name": "frete.md",
                            "file": {},
                            "eTag": "v2",
                            "size": 3,
                            "@microsoft.graph.downloadUrl": "https://acme.sharepoint.com/download/2",
                        }
                    ]
                },
            )
        if url == "https://acme.sharepoint.com/download/2":
            return httpx.Response(200, content=b"abc")
        return httpx.Response(404)

    source = SharePointSource(
        SharePointSettings(
            hostname="acme.sharepoint.com",
            site_path="/sites/atendimento",
            folder_path="Procedimentos",
            tenant_id="tenant-1",
            client_id="app-1",
        ),
        {"client_secret": "segredo"},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    files = source.list_files()
    by_path = {f.path: f for f in files}
    assert {p: f.version for p, f in by_path.items()} == {"troca.docx": "v1", "Sub/frete.md": "v2"}
    # o token sai uma vez por sincronização
    assert sum(1 for s in seen if "oauth2" in s) == 1
    assert source.download(by_path["Sub/frete.md"]) == b"abc"
    assert checked == ["https://acme.sharepoint.com/download/2"]


def test_arquivo_fora_do_suportado_ou_grande_fica_de_fora() -> None:
    from app.knowledge.connector_sync import selectable

    files = [
        RemoteFile(path="a.md", version="1", size=10),
        RemoteFile(path="b.png", version="1", size=10),
        RemoteFile(path="c.pdf", version="1", size=10_000),
        RemoteFile(path="vazio.txt", version="1", size=0),
    ]
    chosen, skipped = selectable(files, max_bytes=1_000)
    assert [f.path for f in chosen] == ["a.md"] and skipped == 3


def _overdue(model: Any, row_id: str, column: str) -> None:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import update

    from app.db import get_engine

    with Session(get_engine()) as session:
        session.execute(
            update(model)
            .where(model.id == UUID(row_id))
            .values({column: datetime.now(UTC) - timedelta(minutes=1)})
        )
        session.commit()


def test_url_reindexa_no_intervalo_so_quando_muda(
    client: TestClient, base_id: str, github: FakeGitHub
) -> None:
    from app.knowledge import schedule
    from app.models.knowledge_content import KnowledgeContent

    github.page = "Horário de atendimento: das 8h às 18h."
    created = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/url",
        json={"url": f"{github.url}/pagina", "name": "Horário", "refresh_every_hours": 24},
    ).json()
    content = client.get(f"/api/v1/knowledge-bases/{base_id}/contents/{created['id']}").json()
    assert content["status"] == "completed" and content["refresh_every_hours"] == 24
    assert content["next_refresh_at"] is not None

    # venceu, a página é a mesma: nada de embedding
    _overdue(KnowledgeContent, created["id"], "next_refresh_at")
    tokens = _embedding_tokens(base_id)
    _, urls = schedule.claim_due()
    assert urls == [UUID(created["id"])]
    assert schedule.refresh_url(UUID(created["id"])) is False
    assert _embedding_tokens(base_id) == tokens
    # o próximo horário foi marcado na reivindicação: não volta no minuto seguinte
    assert schedule.claim_due()[1] == []

    github.page = "Horário de atendimento: das 9h às 20h, inclusive sábado."
    _overdue(KnowledgeContent, created["id"], "next_refresh_at")
    _, urls = schedule.claim_due()
    assert schedule.refresh_url(urls[0]) is True
    found = client.post(
        f"/api/v1/knowledge-bases/{base_id}/search", json={"query": "horário de atendimento"}
    ).json()
    texts = " ".join(hit["text"] for hit in found)
    assert "20h" in texts and "18h" not in texts

    # desligar a reindexação; arquivo e texto não têm intervalo
    off = client.put(
        f"/api/v1/knowledge-bases/{base_id}/contents/{created['id']}/schedule",
        json={"refresh_every_hours": None},
    ).json()
    assert off["refresh_every_hours"] is None and off["next_refresh_at"] is None
    text = client.post(
        f"/api/v1/knowledge-bases/{base_id}/contents/text", json={"name": "nota", "text": "oi"}
    ).json()
    resp = client.put(
        f"/api/v1/knowledge-bases/{base_id}/contents/{text['id']}/schedule",
        json={"refresh_every_hours": 24},
    )
    assert resp.status_code == 422


def test_conector_sincroniza_no_intervalo(
    client: TestClient, base_id: str, github: FakeGitHub
) -> None:
    from app.knowledge import schedule
    from app.knowledge.connector_sync import sync
    from app.models.knowledge_connector import KnowledgeConnector

    github.files = {"docs/troca.md": "Troca em 30 dias."}
    connector = client.post(
        f"/api/v1/knowledge-bases/{base_id}/connectors",
        json={
            "kind": "github",
            "name": "Agendado",
            "settings": {"repo": "acme/docs", "path": "docs", "api_url": github.url},
            "sync_every_hours": 6,
        },
    ).json()
    assert connector["sync_every_hours"] == 6 and connector["next_sync_at"] is not None
    assert schedule.claim_due()[0] == []

    _overdue(KnowledgeConnector, connector["id"], "next_sync_at")
    connectors, _ = schedule.claim_due()
    assert connectors == [UUID(connector["id"])]
    claimed = client.get(f"/api/v1/knowledge-bases/{base_id}/connectors").json()[0]
    assert claimed["last_status"] == "running"
    sync(connectors[0])
    done = client.get(f"/api/v1/knowledge-bases/{base_id}/connectors").json()[0]
    assert done["last_status"] == "ok" and done["last_summary"]["added"] == 1
    assert schedule.claim_due()[0] == []


def test_webhook_da_origem_sincroniza_com_assinatura(
    client: TestClient, base_id: str, github: FakeGitHub
) -> None:
    """ADR-0039: rota pública, só com o HMAC do corpo; inclui o filtro por nome."""
    import hashlib
    import hmac

    github.files = {
        "docs/politicas/troca.md": "# Troca\n\nO prazo de troca é de 30 dias.",
        "docs/CHANGELOG.md": "mudanças",
    }
    base = f"/api/v1/knowledge-bases/{base_id}/connectors"
    connector = client.post(
        base,
        json={
            "kind": "github",
            "name": "Políticas",
            "settings": {
                "repo": "acme/docs",
                "path": "docs",
                "api_url": github.url,
                "include": ["politicas/**/*.md"],
            },
        },
    ).json()
    hook = f"/api/v1/knowledge-connectors/{connector['id']}/webhook"
    body = b'{"ref": "refs/heads/main"}'
    assert client.post(hook, content=body).status_code == 404  # sem webhook configurado

    issued = client.post(f"{base}/{connector['id']}/webhook").json()
    assert issued["path"] == hook and len(issued["secret"]) > 30
    assert client.get(base).json()[0]["has_webhook"] is True
    assert issued["secret"] not in json.dumps(client.get(base).json())

    def sign(secret: str) -> str:
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert (
        client.post(hook, content=body, headers={"X-Hub-Signature-256": "sha256=00"}).status_code
        == 401
    )
    assert client.post(hook, content=body).status_code == 401
    ok = client.post(hook, content=body, headers={"X-Hub-Signature-256": sign(issued["secret"])})
    assert ok.status_code == 202, ok.text
    contents = client.get(f"/api/v1/knowledge-bases/{base_id}/contents").json()
    # o filtro deixou o CHANGELOG de fora
    assert [c["external_path"] for c in contents] == ["politicas/troca.md"]
    # uma sincronização por minuto
    again = client.post(
        hook, content=body, headers={"X-Automata-Signature": sign(issued["secret"])}
    )
    assert again.status_code == 429

    # corpo chunked não traz content-length: o teto vale lendo o stream (Fase 43)
    def chunks() -> Any:
        for _ in range(3):
            yield b"x" * 512 * 1024

    big = client.post(hook, content=chunks(), headers={"X-Hub-Signature-256": "sha256=00"})
    assert big.status_code == 413
    bad_length = client.post(hook, content=body, headers={"Content-Length": "abc"})
    assert bad_length.status_code in (400, 413)
    weird = client.post(
        hook, content=body, headers={"X-Automata-Signature": "sha256=é".encode("latin-1")}
    )
    assert weird.status_code == 401
    assert client.delete(f"{base}/{connector['id']}/webhook").status_code == 204
    assert (
        client.post(
            hook, content=body, headers={"X-Hub-Signature-256": sign(issued["secret"])}
        ).status_code
        == 404
    )


@pytest.fixture
def worker_on(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("INGEST_WORKER", "true")
    get_settings.cache_clear()
    yield
    monkeypatch.delenv("INGEST_WORKER")
    get_settings.cache_clear()


def test_worker_de_ingestao_processa_a_fila(
    client: TestClient, base_id: str, github: FakeGitHub, worker_on: None
) -> None:
    """ADR-0039: com INGEST_WORKER a API só enfileira; o worker executa os cinco caminhos."""
    from app.db import get_engine
    from app.knowledge.worker import run_once
    from app.models.ingest_job import IngestJob

    contents = f"/api/v1/knowledge-bases/{base_id}/contents"
    sent = client.post(
        contents + "/text", json={"name": "Troca", "text": "Prazo de troca: 30 dias."}
    )
    assert sent.status_code == 202, sent.text
    assert sent.json()["queued"] is True
    listed = client.get(contents).json()
    assert listed[0]["status"] == "processing" and listed[0]["queued"] is True
    assert _chunks(base_id) == 0  # nada processado no processo da API

    github.files = {"docs/frete.md": "Frete grátis acima de R$ 200."}
    connector = client.post(
        f"/api/v1/knowledge-bases/{base_id}/connectors",
        json={
            "kind": "github",
            "name": "Docs",
            "settings": {"repo": "acme/docs", "path": "docs", "api_url": github.url},
        },
    ).json()
    synced = client.post(f"/api/v1/knowledge-bases/{base_id}/connectors/{connector['id']}/sync")
    assert synced.status_code == 202
    assert len(client.get(contents).json()) == 1  # a sincronização também esperou

    with Session(get_engine()) as session:
        kinds = session.scalars(select(IngestJob.kind).order_by(IngestJob.created_at)).all()
    assert kinds[-2:] == ["ingest", "sync"]

    while run_once():
        pass
    listed = client.get(contents).json()
    assert {c["status"] for c in listed} == {"completed"}
    assert {c["queued"] for c in listed} == {False}
    assert {c["name"] for c in listed} >= {"Troca", "frete"}

    # reprocessamento entra como um job só, com a lista de conteúdos
    assert client.post(f"/api/v1/knowledge-bases/{base_id}/reprocess").status_code == 202
    with Session(get_engine()) as session:
        job = session.scalars(select(IngestJob).where(IngestJob.status == "queued")).one()
    assert job.kind == "reprocess" and len(job.payload["content_ids"]) == 2
    assert run_once() and not run_once()
    assert {c["status"] for c in client.get(contents).json()} == {"completed"}


def test_job_travado_volta_uma_vez_e_depois_falha(
    client: TestClient, base_id: str, worker_on: None
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.db import get_engine
    from app.knowledge.worker import claim, recover_stale
    from app.models.ingest_job import IngestJob

    contents = f"/api/v1/knowledge-bases/{base_id}/contents"
    content_id = client.post(contents + "/text", json={"name": "Travado", "text": "texto"}).json()[
        "id"
    ]
    later = datetime.now(UTC) + timedelta(minutes=31)

    first = claim()
    assert first is not None and str(first.target_id) == content_id
    # worker caiu no meio: volta para a fila
    assert recover_stale(later) == (1, 0)
    second = claim()
    assert second is not None and second.id == first.id
    assert recover_stale(later) == (0, 1)
    with Session(get_engine()) as session:
        job = session.get(IngestJob, first.id)
        assert job is not None and job.status == "failed" and job.attempts == 2
    content = client.get(f"{contents}/{content_id}").json()
    assert content["status"] == "failed" and "worker" in content["status_message"]
