"""Conversas dos canais para quem atende (ADR-0044): assumir, responder, devolver ao
agente e encerrar. Owner e editor (`conversations:handle`)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from starlette.concurrency import run_in_threadpool

from app.audit import note
from app.authz import Scope, require_scopes
from app.channels import service
from app.db import SessionDep
from app.models.channel import Channel, ChannelConversation, ChannelMessage
from app.repositories.user import emails_by_id

router = APIRouter(
    prefix="/api/v1/conversations",
    tags=["conversations"],
    dependencies=[Depends(require_scopes(Scope.CONVERSATIONS_HANDLE))],
)

Status = Literal["bot", "human", "closed"]
MAX_MESSAGES = 200


class ConversationSummary(BaseModel):
    id: UUID
    channel_id: UUID
    channel_name: str
    channel_kind: str
    user_id: str
    status: str
    assigned_to: str | None
    assigned_label: str | None
    handoff_reason: str | None
    last_message: str | None
    last_message_at: datetime


class MessageResponse(BaseModel):
    id: UUID
    direction: str
    author: str
    author_label: str | None
    text: str
    status: str
    error: str | None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[MessageResponse]


class ReplyInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _summaries(
    session: SessionDep, rows: list[tuple[ChannelConversation, Channel]]
) -> list[ConversationSummary]:
    ids = [c.id for c, _ in rows]
    last: dict[UUID, str] = {}
    if ids:
        latest = (
            select(
                ChannelMessage.conversation_id,
                ChannelMessage.text,
                func.row_number()
                .over(
                    partition_by=ChannelMessage.conversation_id,
                    order_by=desc(ChannelMessage.created_at),
                )
                .label("n"),
            )
            .where(ChannelMessage.conversation_id.in_(ids))
            .subquery()
        )
        last = {
            cid: text
            for cid, text in session.execute(
                select(latest.c.conversation_id, latest.c.text).where(latest.c.n == 1)
            )
        }
    labels = emails_by_id(session, {c.assigned_to for c, _ in rows if c.assigned_to})
    return [
        ConversationSummary(
            id=c.id,
            channel_id=ch.id,
            channel_name=ch.name,
            channel_kind=ch.kind,
            user_id=c.user_id,
            status=c.status,
            assigned_to=c.assigned_to,
            assigned_label=labels.get(c.assigned_to) if c.assigned_to else None,
            handoff_reason=c.handoff_reason,
            last_message=(last.get(c.id) or "")[:200] or None,
            last_message_at=c.last_message_at,
        )
        for c, ch in rows
    ]


def _load(
    session: SessionDep, conversation_id: UUID, lock: bool = False
) -> tuple[ChannelConversation, Channel]:
    conv = session.get(ChannelConversation, conversation_id, with_for_update=lock)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    channel = session.get(Channel, conv.channel_id)
    assert channel is not None
    return conv, channel


def _detail(session: SessionDep, conv: ChannelConversation, channel: Channel) -> ConversationDetail:
    (summary,) = _summaries(session, [(conv, channel)])
    messages = list(
        session.scalars(
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conv.id)
            .order_by(desc(ChannelMessage.created_at))
            .limit(MAX_MESSAGES)
        )
    )[::-1]
    attendants = {
        m.author.removeprefix("attendant:") for m in messages if m.author.startswith("attendant:")
    }
    labels = emails_by_id(session, attendants)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[
            MessageResponse(
                id=m.id,
                direction=m.direction,
                author=m.author,
                author_label=labels.get(m.author.removeprefix("attendant:"))
                if m.author.startswith("attendant:")
                else None,
                text=m.text,
                status=m.status,
                error=m.error,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    session: SessionDep,
    status: Status | None = None,
    channel_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConversationSummary]:
    query = select(ChannelConversation, Channel).join(
        Channel, Channel.id == ChannelConversation.channel_id
    )
    if status:
        query = query.where(ChannelConversation.status == status)
    if channel_id:
        query = query.where(ChannelConversation.channel_id == channel_id)
    rows = session.execute(
        query.order_by(desc(ChannelConversation.last_message_at)).limit(limit)
    ).all()
    return _summaries(session, [(c, ch) for c, ch in rows])


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: UUID, session: SessionDep) -> ConversationDetail:
    conv, channel = _load(session, conversation_id)
    return _detail(session, conv, channel)


@router.post("/{conversation_id}/take", response_model=ConversationDetail)
def take(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    conv, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conv.status, status_after="human")
    conv.status = "human"
    conv.assigned_to = _actor(request)
    conv.handoff_reason = conv.handoff_reason or "assumida no painel"
    session.commit()
    return _detail(session, conv, channel)


@router.post("/{conversation_id}/release", response_model=ConversationDetail)
def release(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    """Devolve ao agente: a próxima mensagem do cliente é respondida por ele."""
    conv, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conv.status, status_after="bot")
    conv.status = "bot"
    conv.assigned_to = None
    conv.handoff_reason = None
    session.commit()
    return _detail(session, conv, channel)


@router.post("/{conversation_id}/close", response_model=ConversationDetail)
def close(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    conv, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conv.status, status_after="closed")
    conv.status = "closed"
    session.commit()
    return _detail(session, conv, channel)


@router.post("/{conversation_id}/reply", response_model=ConversationDetail)
async def reply(
    conversation_id: UUID, body: ReplyInput, request: Request, session: SessionDep
) -> ConversationDetail:
    conv, channel = await run_in_threadpool(_load, session, conversation_id)
    if conv.status != "human":
        raise HTTPException(status_code=409, detail="Assuma a conversa antes de responder")
    last_in = await run_in_threadpool(
        lambda: session.scalars(
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conv.id, ChannelMessage.direction == "in")
            .order_by(desc(ChannelMessage.created_at))
            .limit(1)
        ).first()
    )
    reply_to = (last_in.meta or {}).get("reply_to") if last_in is not None else None
    if not reply_to:
        raise HTTPException(status_code=409, detail="A conversa não tem mensagem do cliente")
    actor = _actor(request)
    ok, error = await run_in_threadpool(
        service.deliver, channel, conv.id, reply_to, body.text.strip(), f"attendant:{actor}"
    )
    if conv.assigned_to is None:
        conv.assigned_to = actor
        await run_in_threadpool(session.commit)
    if not ok:
        raise HTTPException(status_code=502, detail=f"O canal recusou a resposta: {error}")
    session.expire_all()
    return await run_in_threadpool(_detail, session, conv, channel)
