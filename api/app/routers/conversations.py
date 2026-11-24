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
    """Quem fez a ação; "panel" quando a requisição não traz usuário."""
    return str(getattr(request.state, "user_id", None) or "panel")


def _summaries(
    session: SessionDep, rows: list[tuple[ChannelConversation, Channel]]
) -> list[ConversationSummary]:
    """Resumo de cada conversa com a última mensagem e o e-mail de quem atende."""
    conversation_ids = [conversation.id for conversation, _ in rows]
    last_text_by_conversation: dict[UUID, str] = {}
    if conversation_ids:
        # última mensagem de cada conversa numa consulta só: numera por conversa, da mais
        # nova para a mais velha, e fica com a primeira
        ranked_messages = (
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
            .where(ChannelMessage.conversation_id.in_(conversation_ids))
            .subquery()
        )
        last_text_by_conversation = {
            conversation_id: text
            for conversation_id, text in session.execute(
                select(ranked_messages.c.conversation_id, ranked_messages.c.text).where(
                    ranked_messages.c.n == 1
                )
            )
        }
    labels = emails_by_id(
        session, {conversation.assigned_to for conversation, _ in rows if conversation.assigned_to}
    )
    return [
        ConversationSummary(
            id=conversation.id,
            channel_id=channel.id,
            channel_name=channel.name,
            channel_kind=channel.kind,
            user_id=conversation.user_id,
            status=conversation.status,
            assigned_to=conversation.assigned_to,
            assigned_label=labels.get(conversation.assigned_to)
            if conversation.assigned_to
            else None,
            handoff_reason=conversation.handoff_reason,
            last_message=(last_text_by_conversation.get(conversation.id) or "")[:200] or None,
            last_message_at=conversation.last_message_at,
        )
        for conversation, channel in rows
    ]


def _load(
    session: SessionDep, conversation_id: UUID, lock: bool = False
) -> tuple[ChannelConversation, Channel]:
    """Conversa e canal dela; com `lock`, trava a conversa contra duas ações ao mesmo tempo."""
    conversation = session.get(ChannelConversation, conversation_id, with_for_update=lock)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    channel = session.get(Channel, conversation.channel_id)
    assert channel is not None
    return conversation, channel


def _detail(
    session: SessionDep, conversation: ChannelConversation, channel: Channel
) -> ConversationDetail:
    """Resumo mais as últimas mensagens em ordem cronológica, com o e-mail do atendente."""
    (summary,) = _summaries(session, [(conversation, channel)])
    messages = list(
        session.scalars(
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conversation.id)
            .order_by(desc(ChannelMessage.created_at))
            .limit(MAX_MESSAGES)
        )
    )[::-1]
    # mensagem do atendente vem com autor `attendant:<user_id>`
    attendants = {
        message.author.removeprefix("attendant:")
        for message in messages
        if message.author.startswith("attendant:")
    }
    labels = emails_by_id(session, attendants)
    return ConversationDetail(
        **summary.model_dump(),
        messages=[
            MessageResponse(
                id=message.id,
                direction=message.direction,
                author=message.author,
                author_label=labels.get(message.author.removeprefix("attendant:"))
                if message.author.startswith("attendant:")
                else None,
                text=message.text,
                status=message.status,
                error=message.error,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    session: SessionDep,
    status: Status | None = None,
    channel_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ConversationSummary]:
    """Conversas mais recentes primeiro, com filtro por status e canal."""
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
    return _summaries(session, [(conversation, channel) for conversation, channel in rows])


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: UUID, session: SessionDep) -> ConversationDetail:
    conversation, channel = _load(session, conversation_id)
    return _detail(session, conversation, channel)


@router.post("/{conversation_id}/take", response_model=ConversationDetail)
def take(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    """O atendente assume: o agente para de responder até a conversa ser devolvida."""
    conversation, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conversation.status, status_after="human")
    conversation.status = "human"
    conversation.assigned_to = _actor(request)
    conversation.handoff_reason = conversation.handoff_reason or "assumida no painel"
    session.commit()
    return _detail(session, conversation, channel)


@router.post("/{conversation_id}/release", response_model=ConversationDetail)
def release(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    """Devolve ao agente: a próxima mensagem do cliente é respondida por ele."""
    conversation, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conversation.status, status_after="bot")
    conversation.status = "bot"
    conversation.assigned_to = None
    conversation.handoff_reason = None
    session.commit()
    return _detail(session, conversation, channel)


@router.post("/{conversation_id}/close", response_model=ConversationDetail)
def close(conversation_id: UUID, request: Request, session: SessionDep) -> ConversationDetail:
    """Encerra a conversa, registrando o status anterior na trilha."""
    conversation, channel = _load(session, conversation_id, lock=True)
    note(request, status_before=conversation.status, status_after="closed")
    conversation.status = "closed"
    session.commit()
    return _detail(session, conversation, channel)


@router.post("/{conversation_id}/reply", response_model=ConversationDetail)
async def reply(
    conversation_id: UUID, body: ReplyInput, request: Request, session: SessionDep
) -> ConversationDetail:
    """Resposta do atendente ao cliente pelo canal; só com a conversa assumida."""
    # a sessão é síncrona: cada acesso ao banco vai para a thread, fora do event loop
    conversation, channel = await run_in_threadpool(_load, session, conversation_id)
    if conversation.status != "human":
        raise HTTPException(status_code=409, detail="Assuma a conversa antes de responder")
    last_in = await run_in_threadpool(
        lambda: session.scalars(
            select(ChannelMessage)
            .where(
                ChannelMessage.conversation_id == conversation.id, ChannelMessage.direction == "in"
            )
            .order_by(desc(ChannelMessage.created_at))
            .limit(1)
        ).first()
    )
    # o destino da resposta (telefone ou canal do Slack) vem da última mensagem recebida
    reply_to = (last_in.meta or {}).get("reply_to") if last_in is not None else None
    if not reply_to:
        raise HTTPException(status_code=409, detail="A conversa não tem mensagem do cliente")
    actor = _actor(request)
    delivered, error = await run_in_threadpool(
        service.deliver, channel, conversation.id, reply_to, body.text.strip(), f"attendant:{actor}"
    )
    if conversation.assigned_to is None:
        conversation.assigned_to = actor
        await run_in_threadpool(session.commit)
    if not delivered:
        raise HTTPException(status_code=502, detail=f"O canal recusou a resposta: {error}")
    # a mensagem enviada foi gravada em outra sessão; recarrega para o detalhe trazê-la
    session.expire_all()
    return await run_in_threadpool(_detail, session, conversation, channel)
