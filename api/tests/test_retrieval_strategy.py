"""Estratégia de recuperação por base (ADR-0017): MMR, recência e a busca de sempre."""

import os
import time
from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.knowledge.embedders import EMBEDDERS
from app.knowledge.ingest import ingest
from app.knowledge.search import search_base
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.settings import get_settings

TROCA = "Prazo de troca: 30 dias corridos a partir do recebimento, com nota fiscal."


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        # embedder local do replay: determinístico e sem chave
        os.environ["DEMO_REPLAY"] = "true"
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("DEMO_REPLAY", None)
        get_settings.cache_clear()


def _base(documents: list[tuple[str, str]], retrieval: dict[str, Any]) -> KnowledgeBase:
    """Ingere na ordem dada: o último fica com a data mais nova."""
    spec = EMBEDDERS["voyage"]
    base_id = uuid4()
    with Session(get_engine(), expire_on_commit=False) as session:
        base = KnowledgeBase(
            id=base_id,
            name=f"estrategia {base_id.hex[:6]}",
            slug=f"est_{base_id.hex[:6]}",
            embedder=spec.name,
            embedder_model=spec.model,
            dimensions=spec.dimensions,
            chunk_size=2000,
            vector_table=f"kb_{base_id.hex}",
            retrieval=retrieval,
            updated_by="teste",
        )
        session.add(base)
        session.commit()
        session.expunge(base)
    for name, text in documents:
        with Session(get_engine()) as session:
            content = KnowledgeContent(
                base_id=base_id,
                name=name,
                source_type="text",
                source=name,
                extension="txt",
                status="processing",
                created_by="teste",
            )
            session.add(content)
            session.commit()
            content_id = content.id
        ingest(content_id, text.encode())
        # datas distintas por documento, para a recência ter o que ordenar
        time.sleep(1.1)
    return base


def _names(base: KnowledgeBase, query: str, limit: int) -> list[str | None]:
    return [h.content_name for h in search_base(base, query, limit)]


DOCS = [
    ("politica de troca", TROCA),
    ("politica de troca (copia)", TROCA),
    ("politica de garantia", "Garantia de 90 dias e troca por defeito com laudo técnico."),
]


def test_sem_estrategia_repetidos_ocupam_o_topo(db_url: str) -> None:
    base = _base(DOCS, {})
    top = _names(base, "prazo de troca com nota fiscal", 2)
    assert set(top) == {"politica de troca", "politica de troca (copia)"}


def test_mmr_resgata_o_documento_diferente(db_url: str) -> None:
    base = _base(DOCS, {"reranker": "mmr", "mmr_lambda": 0.3})
    top = _names(base, "prazo de troca com nota fiscal", 2)
    assert "politica de garantia" in top
    assert len(top) == 2


def test_recencia_poe_a_versao_nova_na_frente_sem_tirar_a_antiga(db_url: str) -> None:
    docs = [
        ("politica 2025", "Prazo de troca: 7 dias corridos a partir do recebimento."),
        ("politica 2026", "Prazo de troca: 30 dias corridos a partir do recebimento."),
    ]
    simple = _base(docs, {})
    recent = _base(
        docs, {"reranker": "recency", "recency_weight": 1.0, "recency_half_life_days": 0.0001}
    )
    query = "prazo de troca a partir do recebimento"
    assert set(_names(simple, query, 2)) == {"politica 2025", "politica 2026"}
    assert _names(recent, query, 2) == ["politica 2026", "politica 2025"]


@pytest.fixture
def client(db_url: str) -> Generator[TestClient, None, None]:
    from app.main import create_app

    with TestClient(
        create_app(auto_provision_dbs=False, enable_auth=False, enable_mcp_server=False)
    ) as c:
        yield c


def test_put_sem_estrategia_mantem_a_gravada(client: TestClient) -> None:
    body = {"name": "base com mmr", "slug": "base_mmr", "description": "x"}
    created = client.post(
        "/api/v1/knowledge-bases",
        json={**body, "retrieval": {"reranker": "mmr", "mmr_lambda": 0.7}},
    )
    assert created.status_code == 201, created.text
    assert created.json()["retrieval"]["reranker"] == "mmr"
    base_id = created.json()["id"]

    kept = client.put(
        f"/api/v1/knowledge-bases/{base_id}", json={"name": "base com mmr", "description": "y"}
    ).json()
    assert (kept["retrieval"]["reranker"], kept["retrieval"]["mmr_lambda"]) == ("mmr", 0.7)
    changed = client.put(
        f"/api/v1/knowledge-bases/{base_id}",
        json={"name": "base com mmr", "retrieval": {"reranker": "none"}},
    ).json()
    assert changed["retrieval"]["reranker"] == "none"
    invalid = client.put(
        f"/api/v1/knowledge-bases/{base_id}",
        json={"name": "base com mmr", "retrieval": {"reranker": "mmr", "mmr_lambda": 2}},
    )
    assert invalid.status_code == 422
