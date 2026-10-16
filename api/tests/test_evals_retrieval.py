"""Evals de recuperação das bases de conhecimento (ADR-0012).

Cada pergunta tem um documento que precisa voltar entre os K primeiros trechos.
A versão literal roda em todo PR com o embedder local do replay; a semântica
mede o embedder real e só roda na suíte noturna.
"""

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.knowledge import demo_content
from app.knowledge.embedders import EMBEDDERS
from app.knowledge.ingest import ingest
from app.knowledge.search import search_base
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.settings import get_settings

K = 3


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


def _base_com_documentos(embedder: str) -> KnowledgeBase:
    spec = EMBEDDERS[embedder]  # type: ignore[index]
    base_id = uuid4()
    # sem expirar no commit: a base sai da sessão e segue usada pela busca
    with Session(get_engine(), expire_on_commit=False) as session:
        base = KnowledgeBase(
            id=base_id,
            name=f"eval {base_id.hex[:6]}",
            slug=f"eval_{base_id.hex[:6]}",
            embedder=spec.name,
            embedder_model=spec.model,
            dimensions=spec.dimensions,
            chunk_size=2000,
            vector_table=f"kb_{base_id.hex}",
            updated_by="eval",
        )
        contents = [
            KnowledgeContent(
                base_id=base_id,
                name=name,
                source_type="text",
                source=name,
                extension="txt",
                status="processing",
                created_by="eval",
            )
            for name in demo_content.DOCUMENTS
        ]
        session.add(base)
        session.add_all(contents)
        session.commit()
        ids = [(c.id, c.name) for c in contents]
        session.expunge(base)
    for content_id, name in ids:
        ingest(content_id, demo_content.DOCUMENTS[name].encode())
    return base


def _recall(base: KnowledgeBase, kind: str | None) -> tuple[float, list[str]]:
    questions = [q for q in demo_content.QUESTIONS if kind is None or q.kind == kind]
    misses = []
    for q in questions:
        hits = search_base(base, q.question, K)
        if q.expected not in [h.content_name for h in hits]:
            misses.append(f"{q.question} → {[h.content_name for h in hits]}")
    return 1 - len(misses) / len(questions), misses


def test_recuperacao_literal_com_embedder_local(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEMO_REPLAY", "true")
    base = _base_com_documentos("voyage")
    recall, misses = _recall(base, "literal")
    assert recall == 1.0, misses


@pytest.mark.nightly
def test_recuperacao_semantica_com_voyage(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.environ.get("VOYAGE_API_KEY"):
        pytest.skip("VOYAGE_API_KEY não definida — pulando eval de recuperação")
    monkeypatch.delenv("DEMO_REPLAY", raising=False)
    get_settings.cache_clear()
    base = _base_com_documentos("voyage")
    recall, misses = _recall(base, None)
    # 12 perguntas: aceita errar 2, desde que não seja das literais
    assert recall >= 0.8, misses
    literal, misses_literal = _recall(base, "literal")
    assert literal == 1.0, misses_literal
