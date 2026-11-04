"""Evals do cross-encoder e dos filtros escolhidos pelo modelo (ADR-0033).

Errar o filtro é trazer o manual do produto errado para o cliente, ou responder
"não encontrei" por causa de um filtro mal escolhido. Errar o cross-encoder é cobrar
por uma ordem que não aconteceu, ou ficar sem busca quando o provedor cai.
"""

import os
from collections.abc import Generator
from typing import Any
from uuid import uuid4

import pytest
from agno.knowledge.document import Document
from alembic.config import Config
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.knowledge.filters import clean_filters, describe
from app.knowledge.rerank import CROSS_ENCODER_PRICES, candidate_limit, cross_encode
from app.schemas.knowledge_base import CROSS_ENCODER_MODELS, CrossEncoderSettings, check_fields
from app.settings import get_settings

# --- sem banco ---


def test_todo_modelo_oferecido_tem_preco() -> None:
    for provider, models in CROSS_ENCODER_MODELS.items():
        for model in models:
            assert CROSS_ENCODER_PRICES[f"{provider}:{model}"] > 0


@pytest.mark.parametrize(
    ("requested", "kept", "ignored"),
    [
        ({"plano": "a"}, {"plano": "a"}, []),
        ({"plano": " a "}, {"plano": "a"}, []),
        ({"plano": "A"}, {}, ["plano=A"]),  # valor é exato: o modelo vê a lista
        ({"produto": "a"}, {}, ["produto=a"]),
        ({"plano": "a", "ano": "1999"}, {"plano": "a"}, ["ano=1999"]),
        ({}, {}, []),
    ],
)
def test_filtro_fica_so_com_o_que_existe(
    requested: dict[str, Any], kept: dict[str, str], ignored: list[str]
) -> None:
    known = {"plano": ["a", "b"], "ano": ["2025", "2026"]}
    assert clean_filters(requested, known) == (kept, ignored)


def test_descricao_cita_os_valores_entre_aspas() -> None:
    text = describe({"plano": ['a "premium"', "b"]})
    # aspas no valor não quebram a lista que o modelo lê
    assert '"a \\"premium\\""' in text and '"b"' in text
    assert describe({}) == ""


@pytest.mark.parametrize(
    "fields",
    [
        {f"c{i}": "x" for i in range(11)},
        {"Plano": "a"},
        {"plano": ""},
        {"plano": "x" * 101},
        {"plano a": "x"},
    ],
)
def test_campos_fora_da_regra_sao_recusados(fields: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        check_fields(fields)


def test_lote_de_candidatos_cresce_com_cross_encoder() -> None:
    from app.models.knowledge_base import KnowledgeBase

    plain = KnowledgeBase(retrieval={})
    cross = KnowledgeBase(retrieval={"cross_encoder": {"provider": "cohere"}})
    assert candidate_limit(plain, 5) == 5
    assert candidate_limit(cross, 5) == 15
    assert candidate_limit(cross, 50) == 100


def test_falha_do_provedor_levanta_para_a_busca_seguir_sem_ele(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agno.knowledge.reranker.cohere import CohereReranker

    def broken(self: Any, query: str, documents: list[Document]) -> list[Document]:
        raise RuntimeError("timeout")

    monkeypatch.setattr(CohereReranker, "_rerank", broken)
    with pytest.raises(RuntimeError):
        cross_encode(CrossEncoderSettings(provider="cohere"), "q", [Document(content="x")])
    # lista vazia não chama o provedor nem custa
    assert cross_encode(CrossEncoderSettings(provider="cohere"), "q", []) == []


# --- com banco: três planos com manuais parecidos ---

MANUAIS = {
    "basico": "Para cancelar o plano básico, ligue para a central e informe o protocolo.",
    "premium": "Para cancelar o plano premium, fale com o gerente da conta por e-mail.",
    "empresas": "Para cancelar o plano empresas, o administrador abre um chamado no portal.",
}
PERGUNTAS = ["como cancelar o plano", "quero cancelar", "cancelamento do contrato"]


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


@pytest.fixture(scope="module")
def base(db_url: str) -> Any:
    from app.db import get_engine
    from app.knowledge.embedders import EMBEDDERS
    from app.knowledge.ingest import ingest
    from app.models.knowledge_base import KnowledgeBase
    from app.models.knowledge_content import KnowledgeContent

    spec = EMBEDDERS["voyage"]
    base_id = uuid4()
    with Session(get_engine(), expire_on_commit=False) as session:
        kb = KnowledgeBase(
            id=base_id,
            name="manuais",
            slug=f"man_{base_id.hex[:6]}",
            embedder=spec.name,
            embedder_model=spec.model,
            dimensions=spec.dimensions,
            chunk_size=2000,
            vector_table=f"kb_{base_id.hex}",
            retrieval={"agentic_filters": True},
            updated_by="eval",
        )
        session.add(kb)
        session.commit()
        session.expunge(kb)
    for plano, text in MANUAIS.items():
        with Session(get_engine()) as session:
            content = KnowledgeContent(
                base_id=base_id,
                name=f"manual {plano}",
                source_type="text",
                source=plano,
                extension="txt",
                status="processing",
                created_by="eval",
                fields={"plano": plano, "tipo": "manual"},
            )
            session.add(content)
            session.commit()
            content_id = content.id
        ingest(content_id, text.encode())
    return kb


@pytest.mark.parametrize("plano", list(MANUAIS))
@pytest.mark.parametrize("pergunta", PERGUNTAS)
def test_filtro_nunca_traz_manual_de_outro_plano(base: Any, plano: str, pergunta: str) -> None:
    from app.knowledge.search import search

    outcome = search(base, pergunta, 5, filters={"plano": plano})
    assert not outcome.filters_dropped
    assert [h.content_name for h in outcome.hits] == [f"manual {plano}"]


def test_filtro_com_dois_campos_e_combinado(base: Any) -> None:
    from app.knowledge.search import search

    both = search(base, "cancelar", 5, filters={"plano": "premium", "tipo": "manual"})
    assert [h.content_name for h in both.hits] == ["manual premium"]


def test_filtro_errado_nao_vira_nada_encontrado(base: Any) -> None:
    from app.knowledge.search import search

    outcome = search(base, "cancelar", 5, filters={"plano": "ouro"})
    assert outcome.filters_dropped
    assert len(outcome.hits) == 3
