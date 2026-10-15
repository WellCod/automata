import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.mcp.egress import EgressDenied, check_url
from app.models.mcp_server import McpServer
from app.repositories.mcp_server import McpServerRepository
from app.schemas.mcp_server import McpServerInput, McpServerResponse, McpToolInfo
from app.secrets import SecretsKeyMissing, encrypt_json

router = APIRouter(
    prefix="/api/v1/mcp-servers",
    tags=["mcp-servers"],
    dependencies=[Depends(require_scopes(Scope.MCP_SERVERS_READ))],
)
logger = logging.getLogger(__name__)

_WRITE = [Depends(require_scopes(Scope.MCP_SERVERS_WRITE))]


def to_response(s: McpServer) -> McpServerResponse:
    tools = (
        [McpToolInfo.model_validate(t) for t in s.tools_snapshot]
        if s.tools_snapshot is not None
        else None
    )
    return McpServerResponse(
        id=s.id,
        name=s.name,
        slug=s.slug,
        url=s.url,
        timeout_seconds=s.timeout_seconds,
        header_names=list(s.header_names),
        tools=tools,
        tools_discovered_at=s.tools_discovered_at,
        updated_by=s.updated_by,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _apply(server: McpServer, body: McpServerInput, author: str) -> None:
    url = str(body.url)
    try:
        check_url(url)
        if body.headers is not None:
            server.headers_encrypted = encrypt_json(body.headers) if body.headers else None
            server.header_names = sorted(body.headers)
    except (EgressDenied, SecretsKeyMissing) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if server.url != url:
        # tools descobertas valem para a URL antiga
        server.tools_snapshot = None
        server.tools_discovered_at = None
    server.name = body.name
    server.slug = body.slug
    server.url = url
    server.timeout_seconds = body.timeout_seconds
    server.updated_by = author


def _get_or_404(repo: McpServerRepository, server_id: UUID) -> McpServer:
    server = repo.get(server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="Servidor MCP não encontrado")
    return server


@router.get("", response_model=list[McpServerResponse])
def list_servers(session: SessionDep) -> list[McpServerResponse]:
    return [to_response(s) for s in McpServerRepository(session).list_all()]


@router.get("/{server_id}", response_model=McpServerResponse)
def get_server(server_id: UUID, session: SessionDep) -> McpServerResponse:
    return to_response(_get_or_404(McpServerRepository(session), server_id))


@router.post("", response_model=McpServerResponse, status_code=201, dependencies=_WRITE)
def create_server(body: McpServerInput, session: SessionDep, request: Request) -> McpServerResponse:
    repo = McpServerRepository(session)
    if repo.find_conflict(body.name, body.slug) is not None:
        raise HTTPException(status_code=409, detail="Já existe servidor com esse nome ou slug")
    server = McpServer(header_names=[], url="")
    _apply(server, body, actor(request))
    repo.add(server)
    session.commit()
    session.refresh(server)
    logger.info("mcp server criado", extra={"server_id": str(server.id), "slug": server.slug})
    return to_response(server)


@router.put("/{server_id}", response_model=McpServerResponse, dependencies=_WRITE)
def update_server(
    server_id: UUID, body: McpServerInput, session: SessionDep, request: Request
) -> McpServerResponse:
    repo = McpServerRepository(session)
    server = _get_or_404(repo, server_id)
    if repo.find_conflict(body.name, body.slug, exclude=server_id) is not None:
        raise HTTPException(status_code=409, detail="Já existe servidor com esse nome ou slug")
    _apply(server, body, actor(request))
    session.commit()
    session.refresh(server)
    logger.info("mcp server alterado", extra={"server_id": str(server.id)})
    return to_response(server)


@router.delete("/{server_id}", status_code=204, dependencies=_WRITE)
def delete_server(server_id: UUID, session: SessionDep) -> None:
    repo = McpServerRepository(session)
    repo.delete(_get_or_404(repo, server_id))
    session.commit()
    logger.info("mcp server removido", extra={"server_id": str(server_id)})
