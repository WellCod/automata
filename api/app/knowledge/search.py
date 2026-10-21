"""Busca numa base, usada pela busca de teste do painel e pela tool do agente (ADR-0012)."""

import logging
from dataclasses import dataclass
from uuid import UUID

from agno.knowledge.query_transformer.hyde import HyDE
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.evals.judge import JudgeUsage, metered
from app.knowledge.rerank import reranker_for
from app.knowledge.runtime import metered as metered_embedder
from app.knowledge.runtime import vector_db_for
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.repositories.embedding_usage import record_embedding_usage
from app.repositories.usage import UsageRepository
from app.schemas.knowledge_base import RetrievalSettings

logger = logging.getLogger(__name__)


@dataclass
class Hit:
    content_id: UUID | None
    content_name: str | None
    source: str | None
    text: str
    score: float | None


@dataclass
class SearchOutcome:
    hits: list[Hit]
    # texto que foi de fato buscado: a resposta hipotética, com HyDE ligado
    searched: str
    hyde_tokens: int = 0


@dataclass(frozen=True)
class Caller:
    """Run que fez a busca, para o consumo do HyDE cair no agente certo."""

    agent_config_id: UUID
    user_id: str
    run_id: str | None = None


def search_base(
    base: KnowledgeBase, query: str, limit: int, *, agent_config_id: UUID | None = None
) -> list[Hit]:
    caller = Caller(agent_config_id, "agent") if agent_config_id else None
    return search(base, query, limit, caller=caller).hits


def _hyde(base: KnowledgeBase, query: str) -> tuple[str, JudgeUsage | None, str | None]:
    """Consulta reescrita, consumo e modelo; sem HyDE ou no modo demo, a pergunta como veio."""
    # app.agents importa a factory, que importa esta busca pela tool
    from app.agents import models_map

    settings = RetrievalSettings.model_validate(base.retrieval or {})
    if not settings.hyde or settings.hyde_model is None or models_map.demo_replay():
        return query, None, None
    model, usage = metered(models_map.resolve_model(settings.hyde_model))
    # se a chamada falha, o Agno devolve a pergunta original: busca pior, não busca nenhuma
    return HyDE(model=model).transform(query), usage, settings.hyde_model


def _record_hyde(caller: Caller, model_id: str, usage: JudgeUsage) -> None:
    if not usage.total_tokens:
        return
    from app.agents.tracking import current_eval_run

    evaluation = current_eval_run.get()
    with Session(get_engine()) as session:
        UsageRepository(session).record_event(
            agent_config_id=caller.agent_config_id,
            user_id=evaluation.actor if evaluation else caller.user_id,
            model_id=model_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost=usage.cost,
            run_id=caller.run_id,
            eval_run_id=evaluation.eval_run_id if evaluation else None,
        )
        session.commit()


def search(
    base: KnowledgeBase,
    query: str,
    limit: int,
    *,
    caller: Caller | None = None,
    plain: bool = False,
) -> SearchOutcome:
    """`plain` ignora a estratégia da base: é o lado "sem" da comparação da busca de teste."""
    searched, usage, hyde_model = (query, None, None) if plain else _hyde(base, query)
    if usage is not None and hyde_model is not None and caller is not None:
        _record_hyde(caller, hyde_model, usage)
    hyde_tokens = usage.total_tokens if usage is not None else 0
    reranker = None if plain else reranker_for(base)
    vector_db = vector_db_for(base, "query", with_dates=reranker is not None)
    if not vector_db.table_exists():
        return SearchOutcome([], searched, hyde_tokens)
    # o search do PgVector engole falha do embedder e devolve vazio, que o agente
    # leria como "nada sobre isso"; embedar antes faz a falha aparecer (e o
    # MeteredEmbedder devolve o mesmo vetor ao search, sem segunda chamada)
    embedder = metered_embedder(vector_db)
    embedder.get_embedding_and_usage(searched)
    # o reranker só resgata trecho que foi buscado: pede um lote maior e corta depois
    docs = vector_db.search(searched, limit=reranker.search_limit(limit) if reranker else limit)
    if reranker is not None:
        try:
            # ordena contra a pergunta original
            docs = reranker.rerank(query, docs, limit)[:limit]
        except Exception as exc:
            # busca sem reordenar é melhor que busca nenhuma
            logger.warning(
                "reranker falhou; busca sem reordenar",
                extra={"base_id": str(base.id), "error": str(exc)},
            )
            docs = docs[:limit]
    record_embedding_usage(
        base_id=base.id,
        model=base.embedder_model,
        tokens=embedder.tokens,
        kind="search",
        agent_config_id=caller.agent_config_id if caller else None,
    )
    ids: set[UUID] = set()
    for doc in docs:
        raw = (doc.meta_data or {}).get("content_id")
        if raw:
            ids.add(UUID(str(raw)))
    names: dict[UUID, str] = {}
    if ids:
        with Session(get_engine()) as session:
            rows = session.execute(
                select(KnowledgeContent.id, KnowledgeContent.name).where(
                    KnowledgeContent.id.in_(ids)
                )
            )
            names = {row.id: row.name for row in rows}
    hits = []
    for doc in docs:
        meta = doc.meta_data or {}
        content_id = UUID(str(meta["content_id"])) if meta.get("content_id") else None
        score = meta.get("similarity_score")
        hits.append(
            Hit(
                content_id=content_id,
                content_name=names.get(content_id) if content_id else None,
                source=meta.get("source"),
                text=doc.content,
                score=float(score) if score is not None else None,
            )
        )
    return SearchOutcome(hits, searched, hyde_tokens)
