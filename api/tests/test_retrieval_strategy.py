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


def test_hyde_busca_com_a_resposta_hipotetica_e_mede(
    db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.agents.models_map as models_map
    from app.knowledge.search import Caller, search
    from app.models.usage import UsageEvent
    from tests.fake_models import FixedReplyModel

    docs = [
        ("uso do produto", "Dicas de uso: lave à mão e guarde em local seco depois de usar."),
        (
            "devolucao",
            "Produtos utilizados não são aceitos para devolução, salvo defeito de fabricação.",
        ),
    ]
    question = "posso devolver depois de usar?"
    simple = _base(docs, {})
    assert _names(simple, question, 1) == ["uso do produto"]

    # o embedder continua o local do replay; só o modelo do HyDE responde de verdade
    monkeypatch.setattr(models_map, "demo_replay", lambda: False)
    monkeypatch.setattr(
        models_map,
        "resolve_model",
        lambda model_id, *a, **k: FixedReplyModel(
            id=model_id,
            reply="Produtos utilizados não são aceitos para devolução.",
            tokens=12,
        ),
    )
    hyde = _base(docs, {"hyde": True, "hyde_model": "gpt-4o-mini"})
    outcome = search(hyde, question, 1)
    assert [h.content_name for h in outcome.hits] == ["devolucao"]
    assert outcome.searched.startswith("Produtos utilizados")
    # busca de teste: sem agente, os tokens só aparecem no resultado
    assert outcome.hyde_tokens == 12

    agent_id = uuid4()
    with Session(get_engine()) as session:
        from app.models.config import AgentConfig

        session.add(
            AgentConfig(id=agent_id, name=f"hyde {agent_id.hex[:6]}", description="x", kind="agent")
        )
        session.commit()
    search(hyde, question, 1, caller=Caller(agent_id, "alice", "run-1"))
    with Session(get_engine()) as session:
        event = session.query(UsageEvent).filter(UsageEvent.agent_config_id == agent_id).one()
    assert (event.model_id, event.total_tokens, event.user_id, event.run_id) == (
        "gpt-4o-mini",
        12,
        "alice",
        "run-1",
    )


def test_hyde_desligado_no_modo_demo(db_url: str) -> None:
    from app.knowledge.search import search

    base = _base(DOCS[:1], {"hyde": True, "hyde_model": "gpt-4o-mini"})
    outcome = search(base, "prazo de troca", 1)
    assert (outcome.searched, outcome.hyde_tokens) == ("prazo de troca", 0)


def test_hyde_exige_modelo_da_matriz(client: TestClient) -> None:
    body = {"name": "base hyde", "slug": "base_hyde"}
    sem = client.post("/api/v1/knowledge-bases", json={**body, "retrieval": {"hyde": True}})
    assert sem.status_code == 422
    fora = client.post(
        "/api/v1/knowledge-bases",
        json={**body, "retrieval": {"hyde": True, "hyde_model": "modelo-inventado"}},
    )
    assert fora.status_code == 422


def test_busca_de_teste_compara_com_e_sem_estrategia(client: TestClient) -> None:

    base = _base(DOCS, {"reranker": "mmr", "mmr_lambda": 0.3})
    resp = client.post(
        f"/api/v1/knowledge-bases/{base.id}/search/compare",
        json={"query": "prazo de troca com nota fiscal", "max_results": 2},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["retrieval"]["reranker"] == "mmr"
    without = {h["content_name"] for h in body["without_strategy"]["hits"]}
    with_ = {h["content_name"] for h in body["with_strategy"]["hits"]}
    assert without == {"politica de troca", "politica de troca (copia)"}
    assert "politica de garantia" in with_
    assert body["with_strategy"]["hyde_tokens"] == 0
