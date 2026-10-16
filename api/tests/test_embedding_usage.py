"""Consumo de embedding: contagem, cache que evita pagar duas vezes e exposição (ADR-0012)."""

import os
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.db import get_engine
from app.knowledge.embedders import EmbeddingFailed, HashEmbedder, MeteredEmbedder
from app.models.embedding_usage import EmbeddingUsage
from app.settings import get_settings


@dataclass
class CountingEmbedder(HashEmbedder):
    """Embedder local que informa tokens como a Voyage (uma palavra, um token)."""

    calls: list[str] = field(default_factory=list)

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        self.calls.append(text)
        return self.get_embedding(text), {"total_tokens": len(text.split())}


@dataclass
class EmptyEmbedder(HashEmbedder):
    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, Any] | None]:
        return [], None


def test_metered_conta_tokens_e_nao_repete_chamada() -> None:
    inner = CountingEmbedder(dimensions=32)
    emb = MeteredEmbedder(inner=inner)
    emb.get_embedding_and_usage("três palavras aqui")
    emb.get_embedding("três palavras aqui")
    emb.get_embedding_and_usage("outra")
    assert inner.calls == ["três palavras aqui", "outra"]
    assert emb.tokens == 4
    assert emb.dimensions == 32


def test_metered_acusa_vetor_vazio() -> None:
    with pytest.raises(EmbeddingFailed):
        MeteredEmbedder(inner=EmptyEmbedder(dimensions=8)).get_embedding("x")


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
def embedder(monkeypatch: pytest.MonkeyPatch) -> CountingEmbedder:
    inner = CountingEmbedder(dimensions=1024)
    monkeypatch.setattr("app.knowledge.runtime.build_embedder", lambda *a: inner)
    return inner


@pytest.fixture
def client(
    db_url: str, monkeypatch: pytest.MonkeyPatch, embedder: CountingEmbedder
) -> Generator[TestClient, None, None]:
    import app.agents.factory as factory
    from app.main import create_app
    from tests.fake_models import ToolCallingModel, tool_args

    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    model = ToolCallingModel(
        id="claude-haiku-4-5", tool_name="buscar_custos", tool_args=tool_args(pergunta="férias")
    )
    monkeypatch.setattr(factory, "resolve_model", lambda *a, **k: model)
    app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _rows(kind: str) -> list[EmbeddingUsage]:
    with Session(get_engine()) as session:
        return list(session.scalars(select(EmbeddingUsage).where(EmbeddingUsage.kind == kind)))


def test_ingestao_busca_e_agente_ficam_registrados(
    client: TestClient, embedder: CountingEmbedder
) -> None:
    base = client.post("/api/v1/knowledge-bases", json={"name": "Custos", "slug": "custos"}).json()
    texto = "Cada colaborador tem trinta dias de férias por ano."
    client.post(
        f"/api/v1/knowledge-bases/{base['id']}/contents/text",
        json={"name": "Férias", "text": texto},
    ).raise_for_status()

    # o primeiro trecho é embedado antes do insert; o cache evita a segunda chamada
    assert embedder.calls.count(texto) == 1
    [ingest] = _rows("ingest")
    assert ingest.tokens == len(texto.split())
    assert ingest.model == "voyage-3.5"
    assert float(ingest.cost or 0) == pytest.approx(ingest.tokens * 0.06 / 1_000_000)

    embedder.calls.clear()
    client.post(
        f"/api/v1/knowledge-bases/{base['id']}/search", json={"query": "dias de férias"}
    ).raise_for_status()
    assert embedder.calls == ["dias de férias"]
    [busca] = _rows("search")
    assert busca.agent_config_id is None

    agent = client.post("/api/v1/configs", json={"name": "rh", "description": "Use para RH"})
    agent_id = agent.json()["id"]
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "rh",
            "description": "Use para RH",
            "payload": {"model_id": "claude-haiku-4-5", "knowledge": [{"base_id": base["id"]}]},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    run = client.post(f"/agents/{agent_id}/runs", data={"message": "férias?", "stream": "false"})
    assert run.status_code == 200, run.text

    do_agente = [r for r in _rows("search") if r.agent_config_id is not None]
    assert len(do_agente) == 1
    assert str(do_agente[0].agent_config_id) == agent_id

    rollup = client.get("/api/v1/usage/rollup", params={"agent_id": agent_id}).json()
    assert rollup[0]["embedding_tokens"] == do_agente[0].tokens

    summary = client.get("/api/v1/metrics/summary").json()
    total = sum(r.tokens for r in _rows("ingest") + _rows("search"))
    assert summary["embedding_tokens"] == total

    detalhe = client.get(f"/api/v1/knowledge-bases/{base['id']}").json()
    assert detalhe["embedding_tokens"] == total
    assert detalhe["embedding_cost"] == pytest.approx(total * 0.06 / 1_000_000)
