"""Evals da Fase 42 (ADR-0039): Drive, filtro por nome, webhook da origem e worker.

Errar a versão do Drive reindexa a pasta toda a cada sincronização (e cobra
embedding); errar o filtro deixa na base o que saiu dele; errar a assinatura abre a
sincronização para qualquer um; errar a reivindicação faz dois workers indexarem o
mesmo documento. Só a reivindicação usa banco, porque o SKIP LOCKED é do Postgres.
"""

import hashlib
import hmac
import os
import threading
from collections.abc import Generator
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.knowledge.connector_sync import plan, selectable
from app.knowledge.google_sources import GDriveSource
from app.knowledge.sources import RemoteFile
from app.routers.connector_webhook import signature_ok
from app.schemas.knowledge_connector import GDriveSettings
from app.settings import get_settings
from tests.test_google_sources import FOLDER, SECRET, Google


def _drive(doc_modified: str) -> list[RemoteFile]:
    folder = [
        {
            "id": "d1",
            "name": "Política de troca",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": doc_modified,
        },
        {
            "id": "f1",
            "name": "manual.pdf",
            "mimeType": "application/pdf",
            "md5Checksum": "abc",
            "size": "2048",
        },
    ]

    def files(request: httpx.Request) -> Any:
        return {"files": folder}

    google = Google({"/drive/v3/files": files})
    return GDriveSource(GDriveSettings(folder_id=FOLDER), SECRET, google.client()).list_files()


def test_drive_docs_e_pdf_viram_dois_documentos_e_editar_o_docs_reindexa_so_ele() -> None:
    first = _drive("2026-11-01T10:00:00Z")
    chosen, skipped = selectable(first, 10 * 1024 * 1024)
    assert sorted(f.path for f in chosen) == ["Política de troca.txt", "manual.pdf"]
    assert skipped == 0

    doc, pdf = uuid4(), uuid4()
    known = {f.path: (doc if f.extension == "txt" else pdf, f.version, "completed") for f in first}
    edited = plan(known, _drive("2026-11-03T08:00:00Z"))
    assert [(f.path, cid) for f, cid in edited.fetch] == [("Política de troca.txt", doc)]
    assert edited.unchanged == 1 and edited.gone == []


def test_filtro_tira_o_changelog_e_mudar_o_filtro_tira_da_base() -> None:
    files = [
        RemoteFile(path="politicas/troca.md", version="1", size=10),
        RemoteFile(path="politicas/2026/frete.md", version="1", size=10),
        RemoteFile(path="CHANGELOG.md", version="1", size=10),
    ]
    only_policies = {"include": ["politicas/**/*.md"]}
    chosen, _ = selectable(files, 1000, only_policies)
    assert sorted(f.path for f in chosen) == ["politicas/2026/frete.md", "politicas/troca.md"]

    troca, frete = uuid4(), uuid4()
    known = {
        "politicas/troca.md": (troca, "1", "completed"),
        "politicas/2026/frete.md": (frete, "1", "completed"),
    }
    narrowed, _ = selectable(files, 1000, {**only_policies, "exclude": ["politicas/2026/**"]})
    result = plan(known, narrowed)
    assert result.gone == [frete] and result.fetch == [] and result.unchanged == 1


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.parametrize(
    ("header", "ok"),
    [
        (_sign("segredo", b'{"ref":"main"}'), True),
        (_sign("segredo", b'{"ref":"main"}').upper().replace("SHA256=", "sha256="), False),
        (_sign("outro", b'{"ref":"main"}'), False),
        (_sign("segredo", b'{"ref":"dev"}'), False),  # corpo trocado no caminho
        (_sign("segredo", b'{"ref":"main"}').removeprefix("sha256="), False),
        ("sha1=" + hashlib.sha1(b"x").hexdigest(), False),
        ("", False),
        (None, False),
    ],
)
def test_assinatura_do_webhook(header: str | None, ok: bool) -> None:
    assert signature_ok("segredo", b'{"ref":"main"}', header) is ok


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old
        get_settings.cache_clear()


def test_dois_workers_nao_pegam_o_mesmo_job(db_url: str) -> None:
    from app.db import get_engine
    from app.knowledge.jobs import enqueue
    from app.knowledge.worker import Claimed, claim

    with Session(get_engine()) as session:
        for _ in range(20):
            enqueue(session, "ingest", uuid4())
        session.commit()

    claimed: list[Claimed] = []
    lock = threading.Lock()
    start = threading.Barrier(4)

    def worker() -> None:
        start.wait()
        while (job := claim()) is not None:
            with lock:
                claimed.append(job)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ids: list[UUID] = [job.id for job in claimed]
    assert len(ids) == 20 and len(set(ids)) == 20
