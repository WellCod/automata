"""Memórias do usuário (ADR-0025): o owner por agente e cada usuário as próprias.

Memória é dado pessoal do usuário final. Só o owner vê as de um agente, para
atender pedido de exclusão; quem conversa pelo painel vê e apaga as suas.
"""

from datetime import UTC, datetime
from uuid import UUID

from agno.db.schemas.memory import UserMemory
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from app.agents import memory_admin
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.config import ConfigRepository

router = APIRouter(
    prefix="/api/v1/configs/{config_id}/memories",
    tags=["memories"],
    dependencies=[Depends(require_scopes(Scope.MEMORIES_ADMIN))],
)
me_router = APIRouter(prefix="/api/v1/me/memories", tags=["memories"])


class MemoryItem(BaseModel):
    memory_id: str
    user_id: str | None
    agent_id: str | None
    agent_name: str | None = None
    memory: str
    topics: list[str]
    updated_at: datetime | None


def _when(epoch: int | None) -> datetime | None:
    return datetime.fromtimestamp(epoch, UTC) if epoch else None


def _item(m: UserMemory, names: dict[str, str] | None = None) -> MemoryItem:
    return MemoryItem(
        memory_id=m.memory_id or "",
        user_id=m.user_id,
        agent_id=m.agent_id,
        agent_name=(names or {}).get(m.agent_id or ""),
        memory=m.memory,
        topics=list(m.topics or []),
        updated_at=_when(m.updated_at or m.created_at),
    )


def _agent_or_404(session: SessionDep, config_id: UUID) -> None:
    if ConfigRepository(session).get_config(config_id) is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")


@router.get("", response_model=list[MemoryItem])
def list_agent_memories(
    config_id: UUID,
    session: SessionDep,
    user_id: str | None = Query(default=None, max_length=255),  # noqa: B008
) -> list[MemoryItem]:
    _agent_or_404(session, config_id)
    return [_item(m) for m in memory_admin.memories(agent_id=str(config_id), user_id=user_id)]


@router.delete("/{memory_id}", status_code=204)
def delete_agent_memory(config_id: UUID, memory_id: str, session: SessionDep) -> Response:
    _agent_or_404(session, config_id)
    found = [m for m in memory_admin.memories(agent_id=str(config_id)) if m.memory_id == memory_id]
    if not found:
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    memory_admin.delete([memory_id])
    return Response(status_code=204)


@router.delete("", status_code=204)
def forget_user(
    config_id: UUID,
    session: SessionDep,
    user_id: str = Query(min_length=1, max_length=255),  # noqa: B008
) -> Response:
    """Pedido de exclusão: tudo o que este agente guardou sobre o usuário."""
    _agent_or_404(session, config_id)
    rows = memory_admin.memories(agent_id=str(config_id), user_id=user_id)
    memory_admin.delete([m.memory_id for m in rows if m.memory_id], user_id=user_id)
    return Response(status_code=204)


def _me(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sem usuário no token")
    return str(user_id)


@me_router.get("", response_model=list[MemoryItem])
def list_my_memories(request: Request, session: SessionDep) -> list[MemoryItem]:
    rows = memory_admin.memories(user_id=_me(request))
    names = memory_admin.agent_name_map(session, {m.agent_id for m in rows if m.agent_id})
    return [_item(m, names) for m in rows]


@me_router.delete("/{memory_id}", status_code=204)
def delete_my_memory(memory_id: str, request: Request) -> Response:
    user_id = _me(request)
    if not any(m.memory_id == memory_id for m in memory_admin.memories(user_id=user_id)):
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    memory_admin.delete([memory_id], user_id=user_id)
    return Response(status_code=204)


@me_router.delete("", status_code=204)
def forget_me(request: Request) -> Response:
    user_id = _me(request)
    rows = memory_admin.memories(user_id=user_id)
    memory_admin.delete([m.memory_id for m in rows if m.memory_id], user_id=user_id)
    return Response(status_code=204)
