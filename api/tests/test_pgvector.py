"""Fumaça do RAG (ADR-0012): extensão vector, pgvector e Knowledge do Agno no Postgres real."""

import hashlib
import math
from collections.abc import Generator
from dataclasses import dataclass

import pytest
from agno.knowledge.embedder.base import Embedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector
from sqlalchemy import create_engine, text
from testcontainers.postgres import PostgresContainer

_DIMS = 64


@dataclass
class HashEmbedder(Embedder):
    """Saco de palavras com hash: textos com palavras em comum ficam próximos."""

    dimensions: int | None = _DIMS

    def get_embedding(self, text: str) -> list[float]:
        vec = [0.0] * _DIMS
        for word in text.lower().split():
            vec[int(hashlib.sha256(word.encode()).hexdigest(), 16) % _DIMS] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict[str, int] | None]:
        return self.get_embedding(text), None

    async def async_get_embedding(self, text: str) -> list[float]:
        return self.get_embedding(text)

    async def async_get_embedding_and_usage(
        self, text: str
    ) -> tuple[list[float], dict[str, int] | None]:
        return self.get_embedding(text), None


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        yield pg.get_connection_url().replace("psycopg2", "psycopg")


def test_extensao_vector_disponivel(db_url: str) -> None:
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        version = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()
    engine.dispose()
    assert version


def test_knowledge_insere_e_busca(db_url: str) -> None:
    vector_db = PgVector(table_name="kb_fumaca", db_url=db_url, embedder=HashEmbedder())
    knowledge = Knowledge(name="fumaca", vector_db=vector_db)

    knowledge.insert(
        name="ferias",
        text_content="Política de férias: cada colaborador tem trinta dias de férias por ano.",
    )
    knowledge.insert(
        name="reembolso",
        text_content="Reembolso de despesas de viagem exige nota fiscal em até cinco dias.",
    )

    docs = knowledge.search("quantos dias de férias por ano", max_results=1)

    assert len(docs) == 1
    assert "férias" in docs[0].content
    vector_db.drop()


@pytest.mark.parametrize(
    ("ext", "reader"),
    [
        (".pdf", "PDFReader"),
        (".docx", "DocxReader"),
        (".md", "MarkdownReader"),
        (".txt", "TextReader"),
        (".csv", "CSVReader"),
        (".json", "JSONReader"),
    ],
)
def test_leitores_das_extensoes_padrao_instalados(ext: str, reader: str) -> None:
    from agno.knowledge.reader.reader_factory import ReaderFactory

    assert type(ReaderFactory.get_reader_for_extension(ext)).__name__ == reader
