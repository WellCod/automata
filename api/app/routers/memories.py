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
from app.agents.memory import owner_of
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
    """O Agno grava a data da memória em segundos desde a época."""
    return datetime.fromtimestamp(epoch, UTC) if epoch else None


def _item(memory: UserMemory, names: dict[str, str] | None = None) -> MemoryItem:
    """Memória do Agno no formato da resposta; `names` traz o nome do agente ou time dono."""
    return MemoryItem(
        memory_id=memory.memory_id or "",
        user_id=memory.user_id,
        # dono da memória: o agente, ou o time (ADR-0035)
        agent_id=owner_of(memory),
        agent_name=(names or {}).get(owner_of(memory) or ""),
        memory=memory.memory,
        topics=list(memory.topics or []),
        updated_at=_when(memory.updated_at or memory.created_at),
    )


def _agent_or_404(session: SessionDep, config_id: UUID) -> str:
    """Tipo do config (agente ou time), que decide como o Agno guardou o dono."""
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    return str(config.kind)


@router.get("", response_model=list[MemoryItem])
def list_agent_memories(
    config_id: UUID,
    session: SessionDep,
    user_id: str | None = Query(default=None, max_length=255),  # noqa: B008
) -> list[MemoryItem]:
    """Memórias que o agente ou time guardou, de todos os usuários ou de um só."""
    kind = _agent_or_404(session, config_id)
    return [_item(memory) for memory in memory_admin.of_config(str(config_id), kind, user_id)]


@router.delete("/{memory_id}", status_code=204)
def delete_agent_memory(config_id: UUID, memory_id: str, session: SessionDep) -> Response:
    """Apaga uma memória, só se ela pertence a este agente ou time."""
    kind = _agent_or_404(session, config_id)
    matching = [
        memory
        for memory in memory_admin.of_config(str(config_id), kind)
        if memory.memory_id == memory_id
    ]
    if not matching:
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
    kind = _agent_or_404(session, config_id)
    user_memories = memory_admin.of_config(str(config_id), kind, user_id)
    memory_admin.delete(
        [memory.memory_id for memory in user_memories if memory.memory_id], user_id=user_id
    )
    return Response(status_code=204)


def _me(request: Request) -> str:
    """Id de quem chama; sem usuário no token não há memória própria para mostrar."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Sem usuário no token")
    return str(user_id)


@me_router.get("", response_model=list[MemoryItem])
def list_my_memories(request: Request, session: SessionDep) -> list[MemoryItem]:
    """Memórias do próprio usuário em todos os agentes e times, com o nome de cada um."""
    user_memories = memory_admin.memories(user_id=_me(request))
    owners = {owner for memory in user_memories if (owner := owner_of(memory))}
    names = memory_admin.agent_name_map(session, owners)
    return [_item(memory, names) for memory in user_memories]


@me_router.delete("/{memory_id}", status_code=204)
def delete_my_memory(memory_id: str, request: Request) -> Response:
    """Apaga uma memória do próprio usuário; a de outro responde como inexistente."""
    user_id = _me(request)
    if not any(memory.memory_id == memory_id for memory in memory_admin.memories(user_id=user_id)):
        raise HTTPException(status_code=404, detail="Memória não encontrada")
    memory_admin.delete([memory_id], user_id=user_id)
    return Response(status_code=204)


@me_router.delete("", status_code=204)
def forget_me(request: Request) -> Response:
    """Apaga todas as memórias do próprio usuário."""
    user_id = _me(request)
    user_memories = memory_admin.memories(user_id=user_id)
    memory_admin.delete(
        [memory.memory_id for memory in user_memories if memory.memory_id], user_id=user_id
    )
    return Response(status_code=204)
