"""Cadastro e busca de teste das bases de conhecimento (ADR-0012)."""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select

from app.agents.capabilities import get_capabilities
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.knowledge.embedders import EMBEDDERS, is_configured
from app.knowledge.filters import field_values
from app.knowledge.ingest import IngestError, read_documents
from app.knowledge.jobs import submit
from app.knowledge.reprocess import plan_reprocess
from app.knowledge.rerank import CROSS_ENCODER_PRICES, cross_encoder_available
from app.knowledge.search import SearchOutcome, search_base
from app.knowledge.search import search as run_search
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent, KnowledgeContentOriginal
from app.proxy import get_client_ip
from app.repositories.embedding_usage import EmbeddingTotals, EmbeddingUsageRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.routers.knowledge_contents import to_response as content_response
from app.schemas.knowledge_base import (
    CROSS_ENCODER_MODELS,
    ChunkingSettings,
    ChunkPreview,
    ChunkPreviewInput,
    CrossEncoderInfo,
    EmbedderInfo,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    ReprocessResult,
    RetrievalSettings,
    SearchComparison,
    SearchHit,
    SearchInput,
    SearchResult,
    overlap_problem,
)
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/knowledge-bases",
    tags=["knowledge-bases"],
    dependencies=[Depends(require_scopes(Scope.KNOWLEDGE_READ))],
)
logger = logging.getLogger(__name__)

_WRITE = [Depends(require_scopes(Scope.KNOWLEDGE_WRITE))]


def to_response(b: KnowledgeBase, usage: EmbeddingTotals | None = None) -> KnowledgeBaseResponse:
    """Base com a estratégia de busca, o corte e o consumo de embedding somado."""
    return KnowledgeBaseResponse(
        id=b.id,
        name=b.name,
        slug=b.slug,
        description=b.description,
        embedder=b.embedder,
        embedder_model=b.embedder_model,
        dimensions=b.dimensions,
        chunk_size=b.chunk_size,
        retrieval=RetrievalSettings.model_validate(b.retrieval or {}),
        chunking=ChunkingSettings.model_validate(b.chunking or {}),
        embedding_tokens=usage.tokens if usage else 0,
        embedding_cost=usage.cost if usage else None,
        updated_by=b.updated_by,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def _check_retrieval(retrieval: RetrievalSettings | None) -> None:
    """Recusa cross-encoder sem chave na instância e modelo do HyDE desconhecido."""
    if retrieval is None:
        return
    cross_encoder = retrieval.cross_encoder
    if cross_encoder is not None and not cross_encoder_available(cross_encoder.provider):
        raise HTTPException(
            status_code=422,
            detail=f"Cross-encoder {cross_encoder.provider} não configurado na instância",
        )
    if not retrieval.hyde or retrieval.hyde_model is None:
        return
    try:
        get_capabilities(retrieval.hyde_model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _actor(request: Request) -> str:
    """Quem fez a escrita; "panel" quando a requisição não traz usuário."""
    return str(getattr(request.state, "user_id", None) or "panel")


def _get_or_404(base_repo: KnowledgeBaseRepository, base_id: UUID) -> KnowledgeBase:
    base = base_repo.get(base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="Base de conhecimento não encontrada")
    return base


@router.get("/embedders", response_model=list[EmbedderInfo])
def list_embedders() -> list[EmbedderInfo]:
    """Embedders conhecidos, se têm chave na instância e qual é o padrão."""
    default_embedder = get_settings().knowledge_default_embedder
    return [
        EmbedderInfo(
            name=spec.name,
            model=spec.model,
            dimensions=spec.dimensions,
            configured=is_configured(spec),
            default=spec.name == default_embedder,
        )
        for spec in EMBEDDERS.values()
    ]


@router.get("/{base_id}/fields", response_model=dict[str, list[str]])
def get_field_values(base_id: UUID, session: SessionDep) -> dict[str, list[str]]:
    """Campos e valores dos documentos prontos da base: o que o modelo vê na tool."""
    _get_or_404(KnowledgeBaseRepository(session), base_id)
    return field_values(base_id)


@router.get("/cross-encoders", response_model=list[CrossEncoderInfo])
def list_cross_encoders() -> list[CrossEncoderInfo]:
    """Cross-encoders por provedor, com os modelos e o preço de cada busca."""
    return [
        CrossEncoderInfo(
            provider=provider,
            models=list(models),
            configured=cross_encoder_available(provider),
            price_per_search={
                model: CROSS_ENCODER_PRICES.get(f"{provider}:{model}", 0.0) for model in models
            },
        )
        for provider, models in CROSS_ENCODER_MODELS.items()
    ]


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_bases(session: SessionDep) -> list[KnowledgeBaseResponse]:
    bases = KnowledgeBaseRepository(session).list_all()
    usage = EmbeddingUsageRepository(session).by_base([base.id for base in bases])
    return [to_response(base, usage.get(base.id)) for base in bases]


@router.get("/{base_id}", response_model=KnowledgeBaseResponse)
def get_base(base_id: UUID, session: SessionDep) -> KnowledgeBaseResponse:
    base = _get_or_404(KnowledgeBaseRepository(session), base_id)
    usage = EmbeddingUsageRepository(session).by_base([base.id])
    return to_response(base, usage.get(base.id))


@router.post("", response_model=KnowledgeBaseResponse, status_code=201, dependencies=_WRITE)
def create_base(
    body: KnowledgeBaseCreate, session: SessionDep, request: Request
) -> KnowledgeBaseResponse:
    """Cria a base com o embedder escolhido, que fica fixo: trocar exigiria reindexar."""
    _check_retrieval(body.retrieval)
    base_repo = KnowledgeBaseRepository(session)
    if base_repo.find_conflict(body.name, body.slug) is not None:
        raise HTTPException(status_code=409, detail="Já existe base com esse nome ou slug")
    spec = EMBEDDERS[body.embedder or get_settings().knowledge_default_embedder]
    if not is_configured(spec):
        raise HTTPException(
            status_code=422,
            detail=f"Embedder {spec.name} sem chave: defina {spec.key_env} na API",
        )
    base_id = uuid4()
    base = KnowledgeBase(
        id=base_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        embedder=spec.name,
        embedder_model=spec.model,
        dimensions=spec.dimensions,
        chunk_size=body.chunk_size,
        retrieval=(body.retrieval or RetrievalSettings()).model_dump(),
        chunking=(body.chunking or ChunkingSettings()).model_dump(),
        vector_table=f"kb_{base_id.hex}",
        updated_by=_actor(request),
    )
    base_repo.add(base)
    session.commit()
    session.refresh(base)
    logger.info(
        "base de conhecimento criada",
        extra={"base_id": str(base.id), "slug": base.slug, "embedder": base.embedder},
    )
    return to_response(base)


@router.put("/{base_id}", response_model=KnowledgeBaseResponse, dependencies=_WRITE)
def update_base(
    base_id: UUID, body: KnowledgeBaseUpdate, session: SessionDep, request: Request
) -> KnowledgeBaseResponse:
    """Altera nome, descrição, corte e estratégia; o corte novo vale para o que entrar depois."""
    _check_retrieval(body.retrieval)
    base_repo = KnowledgeBaseRepository(session)
    base = _get_or_404(base_repo, base_id)
    if base_repo.find_conflict(body.name, exclude=base_id) is not None:
        raise HTTPException(status_code=409, detail="Já existe base com esse nome")
    base.name = body.name
    base.description = body.description
    chunking = body.chunking or ChunkingSettings.model_validate(base.chunking or {})
    problem = overlap_problem(body.chunk_size, chunking)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    base.chunk_size = body.chunk_size
    base.chunking = chunking.model_dump()
    if body.retrieval is not None:
        base.retrieval = body.retrieval.model_dump()
    base.updated_by = _actor(request)
    session.commit()
    session.refresh(base)
    logger.info("base de conhecimento alterada", extra={"base_id": str(base.id)})
    return to_response(base)


@router.delete("/{base_id}", status_code=204, dependencies=_WRITE)
def delete_base(base_id: UUID, session: SessionDep) -> None:
    """Remove a base; recusa com 409 enquanto algum agente ou time usa ela."""
    base_repo = KnowledgeBaseRepository(session)
    base = _get_or_404(base_repo, base_id)
    configs_using = base_repo.used_by(base_id)
    if configs_using:
        raise HTTPException(
            status_code=409,
            detail=f"Base usada por: {', '.join(configs_using)}. Desligue antes de remover.",
        )
    base_repo.delete(base)
    session.commit()
    logger.info("base de conhecimento removida", extra={"base_id": str(base_id)})


# cada busca paga embedding (e HyDE, no compare): limite por usuário, por minuto
_SEARCH_LIMIT = 30
_SEARCH_FAILED = "Busca falhou: confira a chave do embedder da base e o provedor"


def _limit_search(request: Request) -> None:
    """Limita a busca de teste por usuário, ou por IP quando não há usuário."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        caller = getattr(request.state, "user_id", None) or get_client_ip(request)
        limiter.check(f"kb-search:{caller}", limit=_SEARCH_LIMIT)


@router.post("/{base_id}/search", response_model=list[SearchHit])
def search(
    base_id: UUID, body: SearchInput, session: SessionDep, request: Request
) -> list[SearchHit]:
    """Trechos que o agente receberia para a pergunta, sem rodar o agente."""
    _limit_search(request)
    base = _get_or_404(KnowledgeBaseRepository(session), base_id)
    try:
        hits = search_base(base, body.query, body.max_results, filters=body.filters)
    except Exception as exc:
        # embedder sem chave ou fora do ar: o detalhe do provedor fica só no log
        logger.warning("busca falhou", extra={"base_id": str(base_id), "error": str(exc)})
        raise HTTPException(status_code=502, detail=_SEARCH_FAILED) from exc
    return [SearchHit(**hit.__dict__) for hit in hits]


def _result(outcome: SearchOutcome) -> SearchResult:
    """Resultado da busca com o custo de HyDE e do cross-encoder e os filtros ignorados."""
    return SearchResult(
        hits=[SearchHit(**hit.__dict__) for hit in outcome.hits],
        searched=outcome.searched,
        hyde_tokens=outcome.hyde_tokens,
        rerank_cost=outcome.rerank_cost,
        filters_dropped=outcome.filters_dropped,
    )


@router.post("/{base_id}/search/compare", response_model=SearchComparison)
def compare_search(
    base_id: UUID, body: SearchInput, session: SessionDep, request: Request
) -> SearchComparison:
    """A mesma pergunta com a estratégia da base e com a busca simples, lado a lado."""
    _limit_search(request)
    base = _get_or_404(KnowledgeBaseRepository(session), base_id)
    try:
        with_strategy = run_search(base, body.query, body.max_results, filters=body.filters)
        without_strategy = run_search(
            base, body.query, body.max_results, plain=True, filters=body.filters
        )
    except Exception as exc:
        logger.warning("busca falhou", extra={"base_id": str(base_id), "error": str(exc)})
        raise HTTPException(status_code=502, detail=_SEARCH_FAILED) from exc
    return SearchComparison(
        with_strategy=_result(with_strategy),
        without_strategy=_result(without_strategy),
        retrieval=RetrievalSettings.model_validate(base.retrieval or {}),
    )


_PREVIEW_CHUNKS = 20
# a prévia lê e corta o original inteiro, numa rota síncrona (auditoria da Fase 33)
_PREVIEW_LIMIT = 20
PREVIEW_MAX_BYTES = 2 * 1024 * 1024
# cada reprocessamento embeda a base inteira de novo
_REPROCESS_LIMIT = 1


def _limit(request: Request, key: str, limit: int) -> None:
    """Aplica o limitador da instância quando ele existe (no teste sem app pode faltar)."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is not None:
        limiter.check(key, limit=limit)


@router.post("/{base_id}/chunk-preview", response_model=ChunkPreview, dependencies=_WRITE)
def chunk_preview(
    base_id: UUID, body: ChunkPreviewInput, session: SessionDep, request: Request
) -> ChunkPreview:
    """Trechos que um texto ou conteúdo daria com o corte escolhido, sem embedding (ADR-0029)."""
    caller = getattr(request.state, "user_id", None) or get_client_ip(request)
    _limit(request, f"kb-preview:{caller}", _PREVIEW_LIMIT)
    base = _get_or_404(KnowledgeBaseRepository(session), base_id)
    chunk_size = body.chunk_size or base.chunk_size
    chunking = body.chunking or ChunkingSettings.model_validate(base.chunking or {})
    problem = overlap_problem(chunk_size, chunking)
    if problem:
        raise HTTPException(status_code=422, detail=problem)
    if body.text is not None:
        name, extension, raw_content = "prévia", "txt", body.text.encode()
    else:
        content = session.get(KnowledgeContent, body.content_id)
        if content is None or content.base_id != base_id:
            raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
        original = session.scalar(
            select(KnowledgeContentOriginal.data).where(
                KnowledgeContentOriginal.content_id == content.id
            )
        )
        if original is None:
            raise HTTPException(
                status_code=422,
                detail="Prévia só de arquivo ou texto enviado com o original guardado",
            )
        if len(original) > PREVIEW_MAX_BYTES:
            raise HTTPException(
                status_code=422,
                detail="Prévia de conteúdo até 2 MB: cole um trecho do documento",
            )
        name, extension, raw_content = content.name, content.extension, original
    try:
        documents = read_documents(name, extension, raw_content, chunk_size, chunking)
    except (IngestError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChunkPreview(
        chunks=[document.content for document in documents[:_PREVIEW_CHUNKS]],
        total=len(documents),
        chunk_size=chunk_size,
        chunking=chunking,
    )


@router.post(
    "/{base_id}/reprocess", response_model=ReprocessResult, status_code=202, dependencies=_WRITE
)
def reprocess_base(
    base_id: UUID, session: SessionDep, background: BackgroundTasks, request: Request
) -> ReprocessResult:
    """Reindexa o conteúdo da base com o corte atual; o embedding é cobrado de novo."""
    _get_or_404(KnowledgeBaseRepository(session), base_id)
    _limit(request, f"kb-reprocess:{base_id}", _REPROCESS_LIMIT)
    plan = plan_reprocess(session, base_id)
    session.commit()
    if plan.queued:
        submit(
            background,
            "reprocess",
            base_id,
            {"content_ids": [str(content_id) for content_id in plan.queued]},
        )
    logger.info(
        "base reprocessada",
        extra={"base_id": str(base_id), "queued": len(plan.queued), "skipped": plan.skipped},
    )
    return ReprocessResult(
        queued=len(plan.queued),
        needs_upload=[content_response(content) for content in plan.needs_upload],
        skipped=plan.skipped,
    )
