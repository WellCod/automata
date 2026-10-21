"""Conteúdo das bases: upload de arquivo, URL e texto, processados em background (ADR-0012)."""

import logging
from pathlib import PurePath
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.authz import Scope, require_scopes
from app.db import SessionDep, get_engine
from app.knowledge.fetch import FetchFailed, fetch_url
from app.knowledge.ingest import CONTENT_TYPES, ingest, remove_chunks
from app.knowledge.schedule import next_at, refresh_url
from app.mcp.egress import EgressDenied, check_url
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_content import KnowledgeContent
from app.schemas.knowledge_base import (
    ContentScheduleInput,
    KnowledgeContentResponse,
    TextContentInput,
    UrlContentInput,
)
from app.settings import get_settings

router = APIRouter(
    prefix="/api/v1/knowledge-bases/{base_id}/contents",
    tags=["knowledge-bases"],
    dependencies=[Depends(require_scopes(Scope.KNOWLEDGE_READ))],
)
logger = logging.getLogger(__name__)

_WRITE = [Depends(require_scopes(Scope.KNOWLEDGE_WRITE))]


def to_response(c: KnowledgeContent) -> KnowledgeContentResponse:
    return KnowledgeContentResponse(
        id=c.id,
        base_id=c.base_id,
        name=c.name,
        source_type=c.source_type,
        source=c.source,
        extension=c.extension,
        size_bytes=c.size_bytes,
        status=c.status,
        status_message=c.status_message,
        chunk_count=c.chunk_count,
        created_by=c.created_by,
        created_at=c.created_at,
        updated_at=c.updated_at,
        connector_id=c.connector_id,
        external_path=c.external_path,
        refresh_every_hours=c.refresh_every_hours,
        next_refresh_at=c.next_refresh_at,
    )


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _max_bytes() -> int:
    return get_settings().knowledge_max_upload_mb * 1024 * 1024


def _base_or_404(session: Session, base_id: UUID) -> KnowledgeBase:
    base = session.get(KnowledgeBase, base_id)
    if base is None:
        raise HTTPException(status_code=404, detail="Base de conhecimento não encontrada")
    return base


def _content_or_404(session: Session, base_id: UUID, content_id: UUID) -> KnowledgeContent:
    content = session.get(KnowledgeContent, content_id)
    if content is None or content.base_id != base_id:
        raise HTTPException(status_code=404, detail="Conteúdo não encontrado")
    return content


def _register(session: Session, content: KnowledgeContent) -> KnowledgeContent:
    session.add(content)
    session.commit()
    session.refresh(content)
    logger.info(
        "conteúdo recebido",
        extra={"content_id": str(content.id), "base_id": str(content.base_id)},
    )
    return content


def _ingest_url(content_id: UUID, url: str) -> None:
    """Baixa na thread de background: a resposta do POST não espera o site."""
    try:
        fetched = fetch_url(url, _max_bytes())
        extension = CONTENT_TYPES.get(fetched.content_type)
        if extension is None:
            raise FetchFailed(f"tipo de conteúdo não suportado: {fetched.content_type or '?'}")
    except (FetchFailed, EgressDenied, OSError) as exc:
        with Session(get_engine()) as session:
            session.execute(
                update(KnowledgeContent)
                .where(KnowledgeContent.id == content_id)
                .values(status="failed", status_message=str(exc)[:500])
            )
            session.commit()
        logger.warning("download falhou", extra={"content_id": str(content_id), "error": str(exc)})
        return
    with Session(get_engine()) as session:
        session.execute(
            update(KnowledgeContent)
            .where(KnowledgeContent.id == content_id)
            .values(extension=extension, size_bytes=len(fetched.data))
        )
        session.commit()
    ingest(content_id, fetched.data)


@router.get("", response_model=list[KnowledgeContentResponse])
def list_contents(base_id: UUID, session: SessionDep) -> list[KnowledgeContentResponse]:
    _base_or_404(session, base_id)
    rows = session.scalars(
        select(KnowledgeContent)
        .where(KnowledgeContent.base_id == base_id)
        .order_by(KnowledgeContent.created_at.desc())
    )
    return [to_response(c) for c in rows]


@router.get("/{content_id}", response_model=KnowledgeContentResponse)
def get_content(base_id: UUID, content_id: UUID, session: SessionDep) -> KnowledgeContentResponse:
    return to_response(_content_or_404(session, base_id, content_id))


@router.post("/file", response_model=KnowledgeContentResponse, status_code=202, dependencies=_WRITE)
def upload_file(
    base_id: UUID,
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),  # noqa: B008
    name: str | None = Form(default=None),  # noqa: B008
) -> KnowledgeContentResponse:
    _base_or_404(session, base_id)
    filename = PurePath(file.filename or "arquivo").name
    extension = PurePath(filename).suffix.lower().lstrip(".")
    allowed = get_settings().knowledge_extensions
    if extension not in allowed:
        aceitas = ", ".join(sorted(allowed))
        raise HTTPException(
            status_code=415, detail=f"Extensão .{extension or '?'} não aceita (aceitas: {aceitas})"
        )
    limit = _max_bytes()
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status_code=413, detail=f"Arquivo maior que {limit // (1024 * 1024)} MB"
        )
    if not data:
        raise HTTPException(status_code=422, detail="Arquivo vazio")
    content = _register(
        session,
        KnowledgeContent(
            base_id=base_id,
            name=(name or PurePath(filename).stem)[:255],
            source_type="file",
            source=filename,
            extension=extension,
            size_bytes=len(data),
            status="processing",
            created_by=_actor(request),
        ),
    )
    background.add_task(ingest, content.id, data)
    return to_response(content)


@router.post("/url", response_model=KnowledgeContentResponse, status_code=202, dependencies=_WRITE)
def add_url(
    base_id: UUID,
    body: UrlContentInput,
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
) -> KnowledgeContentResponse:
    _base_or_404(session, base_id)
    url = str(body.url)
    try:
        check_url(url)
    except EgressDenied as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    content = _register(
        session,
        KnowledgeContent(
            base_id=base_id,
            name=(body.name or url)[:255],
            source_type="url",
            source=url,
            extension="html",
            status="processing",
            created_by=_actor(request),
            refresh_every_hours=body.refresh_every_hours,
            next_refresh_at=next_at(body.refresh_every_hours),
        ),
    )
    background.add_task(_ingest_url, content.id, url)
    return to_response(content)


@router.post("/text", response_model=KnowledgeContentResponse, status_code=202, dependencies=_WRITE)
def add_text(
    base_id: UUID,
    body: TextContentInput,
    session: SessionDep,
    request: Request,
    background: BackgroundTasks,
) -> KnowledgeContentResponse:
    _base_or_404(session, base_id)
    data = body.text.encode()
    if len(data) > _max_bytes():
        raise HTTPException(status_code=413, detail="Texto maior que o limite de upload")
    content = _register(
        session,
        KnowledgeContent(
            base_id=base_id,
            name=body.name,
            source_type="text",
            source=body.name,
            extension="txt",
            size_bytes=len(data),
            status="processing",
            created_by=_actor(request),
        ),
    )
    background.add_task(ingest, content.id, data)
    return to_response(content)


@router.put("/{content_id}/schedule", response_model=KnowledgeContentResponse, dependencies=_WRITE)
def update_schedule(
    base_id: UUID, content_id: UUID, body: ContentScheduleInput, session: SessionDep
) -> KnowledgeContentResponse:
    """Intervalo de reindexação de uma URL; vazio desliga."""
    content = _content_or_404(session, base_id, content_id)
    if content.source_type != "url":
        raise HTTPException(status_code=422, detail="Só conteúdo de URL é reindexado no intervalo")
    content.refresh_every_hours = body.refresh_every_hours
    content.next_refresh_at = next_at(body.refresh_every_hours)
    session.commit()
    session.refresh(content)
    return to_response(content)


@router.post(
    "/{content_id}/refresh",
    response_model=KnowledgeContentResponse,
    status_code=202,
    dependencies=_WRITE,
)
def refresh_content(
    base_id: UUID, content_id: UUID, session: SessionDep, background: BackgroundTasks
) -> KnowledgeContentResponse:
    """Baixa a URL agora; só reindexa se o conteúdo mudou."""
    content = _content_or_404(session, base_id, content_id)
    if content.source_type != "url":
        raise HTTPException(status_code=422, detail="Só conteúdo de URL é baixado de novo")
    if content.status == "processing":
        raise HTTPException(status_code=409, detail="Conteúdo em processamento")
    background.add_task(refresh_url, content.id)
    return to_response(content)


@router.delete("/{content_id}", status_code=204, dependencies=_WRITE)
def delete_content(base_id: UUID, content_id: UUID, session: SessionDep) -> None:
    base = _base_or_404(session, base_id)
    content = _content_or_404(session, base_id, content_id)
    remove_chunks(base, content.id)
    session.delete(content)
    session.commit()
    logger.info("conteúdo removido", extra={"content_id": str(content_id)})
