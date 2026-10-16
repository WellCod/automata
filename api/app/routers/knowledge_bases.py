"""Cadastro e busca de teste das bases de conhecimento (ADR-0012)."""

import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.knowledge.embedders import EMBEDDERS, is_configured
from app.knowledge.search import search_base
from app.models.knowledge_base import KnowledgeBase
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    EmbedderInfo,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    SearchHit,
    SearchInput,
)
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/knowledge-bases",
    tags=["knowledge-bases"],
    dependencies=[Depends(require_scopes(Scope.KNOWLEDGE_READ))],
)
logger = logging.getLogger(__name__)

_WRITE = [Depends(require_scopes(Scope.KNOWLEDGE_WRITE))]


def to_response(b: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=b.id,
        name=b.name,
        slug=b.slug,
        description=b.description,
        embedder=b.embedder,
        embedder_model=b.embedder_model,
        dimensions=b.dimensions,
        chunk_size=b.chunk_size,
        updated_by=b.updated_by,
        created_at=b.created_at,
        updated_at=b.updated_at,
    )


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _get_or_404(repo: KnowledgeBaseRepository, base_id: UUID) -> KnowledgeBase:
    base = repo.get(base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="Base de conhecimento não encontrada")
    return base


@router.get("/embedders", response_model=list[EmbedderInfo])
def list_embedders() -> list[EmbedderInfo]:
    default = get_settings().knowledge_default_embedder
    return [
        EmbedderInfo(
            name=spec.name,
            model=spec.model,
            dimensions=spec.dimensions,
            configured=is_configured(spec),
            default=spec.name == default,
        )
        for spec in EMBEDDERS.values()
    ]


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_bases(session: SessionDep) -> list[KnowledgeBaseResponse]:
    return [to_response(b) for b in KnowledgeBaseRepository(session).list_all()]


@router.get("/{base_id}", response_model=KnowledgeBaseResponse)
def get_base(base_id: UUID, session: SessionDep) -> KnowledgeBaseResponse:
    return to_response(_get_or_404(KnowledgeBaseRepository(session), base_id))


@router.post("", response_model=KnowledgeBaseResponse, status_code=201, dependencies=_WRITE)
def create_base(
    body: KnowledgeBaseCreate, session: SessionDep, request: Request
) -> KnowledgeBaseResponse:
    repo = KnowledgeBaseRepository(session)
    if repo.find_conflict(body.name, body.slug) is not None:
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
        vector_table=f"kb_{base_id.hex}",
        updated_by=_actor(request),
    )
    repo.add(base)
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
    repo = KnowledgeBaseRepository(session)
    base = _get_or_404(repo, base_id)
    if repo.find_conflict(body.name, exclude=base_id) is not None:
        raise HTTPException(status_code=409, detail="Já existe base com esse nome")
    base.name = body.name
    base.description = body.description
    base.chunk_size = body.chunk_size
    base.updated_by = _actor(request)
    session.commit()
    session.refresh(base)
    logger.info("base de conhecimento alterada", extra={"base_id": str(base.id)})
    return to_response(base)


@router.delete("/{base_id}", status_code=204, dependencies=_WRITE)
def delete_base(base_id: UUID, session: SessionDep) -> None:
    repo = KnowledgeBaseRepository(session)
    repo.delete(_get_or_404(repo, base_id))
    session.commit()
    logger.info("base de conhecimento removida", extra={"base_id": str(base_id)})


@router.post("/{base_id}/search", response_model=list[SearchHit])
def search(base_id: UUID, body: SearchInput, session: SessionDep) -> list[SearchHit]:
    """Trechos que o agente receberia para a pergunta, sem rodar o agente."""
    base = _get_or_404(KnowledgeBaseRepository(session), base_id)
    try:
        hits = search_base(base, body.query, body.max_results)
    except Exception as exc:
        # embedder sem chave ou fora do ar: erro de configuração, não da API
        logger.warning("busca falhou", extra={"base_id": str(base_id), "error": str(exc)})
        raise HTTPException(status_code=502, detail=f"Busca falhou: {exc}") from exc
    return [SearchHit(**hit.__dict__) for hit in hits]
