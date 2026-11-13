"""Mensagem recebida num canal até a resposta do agente (ADR-0044).

A rota pública só confere a assinatura e agenda este processamento: o provedor reenvia
o que não recebe 200 a tempo. Aqui a mensagem é gravada (o id externo único descarta o
reenvio), a conversa é achada ou criada e, com a conversa no bot, o agente responde.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.channels import providers
from app.db import get_db, get_engine
from app.models.channel import Channel, ChannelConversation, ChannelMessage
from app.models.config import AgentConfig
from app.secrets import decrypt_json

logger = logging.getLogger(__name__)

ONLY_TEXT = "Por enquanto eu só entendo mensagens de texto."
REASON_KEYWORD = "pedido do cliente"
REASON_PAUSED = "confirmação de tool pendente"
HANDOFF_TOOL = "transferir_para_atendente"
LATE_REPLY = "não enviada: a conversa passou para um atendente antes da resposta"
FAILED = "Não consegui responder agora. Tente de novo em instantes."
# mensagens por minuto de uma pessoa num canal: um número não queima o orçamento do agente
PER_SENDER_LIMIT = 20


@dataclass(frozen=True)
class Saved:
    conversation_id: UUID
    user_id: str
    status: str
    message_id: UUID


def _save_inbound(channel_id: UUID, kind: str, msg: providers.Inbound) -> Saved | None:
    """Grava a mensagem; None quando é reenvio do provedor."""
    with Session(get_engine()) as session:
        conv = session.scalars(
            select(ChannelConversation)
            .where(
                ChannelConversation.channel_id == channel_id,
                ChannelConversation.external_id == msg.conversation_key,
            )
            .with_for_update()
        ).first()
        if conv is None:
            # duas mensagens da mesma pessoa nova ao mesmo tempo: a segunda acha a conversa
            session.execute(
                insert(ChannelConversation)
                .values(
                    channel_id=channel_id,
                    external_id=msg.conversation_key,
                    user_id=providers.user_id(kind, msg.sender),
                    status="bot",
                )
                .on_conflict_do_nothing(index_elements=["channel_id", "external_id"])
            )
            conv = session.scalars(
                select(ChannelConversation)
                .where(
                    ChannelConversation.channel_id == channel_id,
                    ChannelConversation.external_id == msg.conversation_key,
                )
                .with_for_update()
            ).one()
        inserted = session.execute(
            insert(ChannelMessage)
            .values(
                channel_id=channel_id,
                conversation_id=conv.id,
                external_id=msg.external_id,
                direction="in",
                author="customer",
                text=msg.text or "",
                status="received",
                meta={"reply_to": msg.reply_to},
            )
            .on_conflict_do_nothing(
                index_elements=["channel_id", "external_id"],
                index_where=ChannelMessage.external_id.is_not(None),
            )
            .returning(ChannelMessage.id)
        ).scalar_one_or_none()
        if inserted is None:
            session.rollback()
            return None
        # conversa encerrada volta ao bot na mensagem nova
        if conv.status == "closed":
            conv.status = "bot"
            conv.assigned_to = None
            conv.handoff_reason = None
        conv.last_message_at = datetime.now(UTC)
        session.commit()
        return Saved(conv.id, conv.user_id, conv.status, inserted)


def record_outbound(
    channel_id: UUID,
    conversation_id: UUID,
    author: str,
    text: str,
    *,
    status: str,
    error: str | None = None,
    external_id: str | None = None,
    run_id: str | None = None,
) -> UUID:
    with Session(get_engine()) as session:
        msg = ChannelMessage(
            channel_id=channel_id,
            conversation_id=conversation_id,
            external_id=f"out:{external_id}" if external_id else None,
            direction="out",
            author=author,
            text=text,
            status=status,
            error=error,
            run_id=run_id,
        )
        session.add(msg)
        conv = session.get(ChannelConversation, conversation_id)
        if conv is not None:
            conv.last_message_at = datetime.now(UTC)
        session.commit()
        return msg.id


def _mark(message_id: UUID, status: str, error: str | None = None) -> None:
    with Session(get_engine()) as session:
        msg = session.get(ChannelMessage, message_id)
        if msg is not None:
            msg.status = status
            msg.error = error
            session.commit()


def deliver(
    channel: Channel,
    conversation_id: UUID,
    reply_to: dict[str, str],
    text: str,
    author: str,
    run_id: str | None = None,
) -> tuple[bool, str | None]:
    """Manda pelo provedor e grava a mensagem de saída, enviada ou com o motivo da falha."""
    creds = decrypt_json(channel.credentials_encrypted)
    try:
        external = providers.send(channel.kind, creds, reply_to, text)
    except providers.SendError as exc:
        record_outbound(
            channel.id,
            conversation_id,
            author,
            text,
            status="failed",
            error=str(exc),
            run_id=run_id,
        )
        return False, str(exc)
    record_outbound(
        channel.id,
        conversation_id,
        author,
        text,
        status="sent",
        external_id=external,
        run_id=run_id,
    )
    return True, None


def _status(conversation_id: UUID) -> str | None:
    with Session(get_engine()) as session:
        conv = session.get(ChannelConversation, conversation_id)
        return conv.status if conv is not None else None


def handoff(conversation_id: UUID, reason: str, assigned_to: str | None = None) -> bool:
    """Passa a conversa para uma pessoa; False quando ela já estava com uma."""
    with Session(get_engine()) as session:
        conv = session.get(ChannelConversation, conversation_id, with_for_update=True)
        if conv is None or conv.status == "human":
            return False
        conv.status = "human"
        conv.handoff_reason = reason[:255]
        conv.assigned_to = assigned_to
        session.commit()
        return True


def wants_human(channel: Channel, text: str) -> bool:
    """Palavra do canal na mensagem, sem diferença de caixa e acento."""
    if not channel.handoff_enabled or not channel.handoff_keywords:
        return False
    words = set(_fold(text).split())
    for keyword in channel.handoff_keywords:
        folded = _fold(keyword)
        if (" " in folded and folded in _fold(text)) or folded in words:
            return True
    return False


def _fold(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return "".join(c if c.isalnum() or c.isspace() else " " for c in plain)


def _handoff_tool(asked: list[str]) -> Any:
    def transferir_para_atendente(motivo: str) -> str:
        """Passa a conversa para uma pessoa da equipe. Use quando o cliente pedir para
        falar com alguém, quando você não puder resolver ou quando o assunto pedir uma
        pessoa. `motivo` é uma frase curta com o porquê.
        """
        asked.append(motivo.strip() or "transferido pelo agente")
        return "Conversa transferida. Avise o cliente que uma pessoa da equipe vai responder."

    return transferir_para_atendente


def _responder(config: AgentConfig, session_id: str, user_id: str) -> Any:
    """O agente ou time do canal, montado como na rota: canário, guardrails, orçamento e
    memória, com o banco do Agno para o histórico da conversa."""
    from app.agents.factory import agent_from, load_team, load_version, team_from

    if config.kind == "team":
        target: Any = team_from(
            config.id, load_team(config.id, None, session_id, canary=True), memory_user=user_id
        )
    else:
        target = agent_from(
            config.id,
            load_version(config.id, None, session_id, canary=True),
            tracked=True,
            memory_user=user_id,
        )
    target.db = get_db()
    return target


def _text(run: Any) -> str:
    content = getattr(run, "content", None)
    if content is None:
        return ""
    return content if isinstance(content, str) else str(content)


async def answer(
    channel: Channel, config: AgentConfig, saved: Saved, text: str, reply: dict[str, str]
) -> None:
    session_id = str(saved.conversation_id)
    asked: list[str] = []
    try:
        target = await asyncio.to_thread(_responder, config, session_id, saved.user_id)
        if channel.handoff_enabled:
            # a tool só existe no run do canal, onde há para quem passar (ADR-0044)
            target.tools = [*(target.tools or []), _handoff_tool(asked)]
        run = await target.arun(text, session_id=session_id, user_id=saved.user_id, stream=False)
    except Exception as exc:
        logger.warning(
            "canal: agente falhou", extra={"channel_id": str(channel.id), "error": str(exc)}
        )
        await asyncio.to_thread(_mark, saved.message_id, "failed", str(exc)[:500])
        await asyncio.to_thread(deliver, channel, saved.conversation_id, reply, FAILED, "system")
        return
    content = _text(run).strip()
    paused = bool(getattr(run, "is_paused", False))
    run_id = getattr(run, "run_id", None)
    if content and not paused:
        # outra mensagem pode ter passado a conversa para uma pessoa enquanto o agente
        # pensava: a resposta fica registrada para o atendente, mas não sai
        if await asyncio.to_thread(_status, saved.conversation_id) != "bot":
            await asyncio.to_thread(
                record_outbound,
                channel.id,
                saved.conversation_id,
                "agent",
                content,
                status="ignored",
                error=LATE_REPLY,
                run_id=run_id,
            )
        else:
            await asyncio.to_thread(
                deliver, channel, saved.conversation_id, reply, content, "agent", run_id
            )
    # run pausado esperando confirmação de tool não tem como seguir pelo canal
    reason = asked[0] if asked else (REASON_PAUSED if paused else None)
    if reason is not None and await asyncio.to_thread(handoff, saved.conversation_id, reason):
        await asyncio.to_thread(
            deliver, channel, saved.conversation_id, reply, channel.handoff_message, "system"
        )


def _load(channel_id: UUID) -> tuple[Channel, AgentConfig] | None:
    with Session(get_engine()) as session:
        channel = session.get(Channel, channel_id)
        if channel is None or not channel.enabled:
            return None
        config = session.get(AgentConfig, channel.config_id)
        if config is None:
            return None
        session.expunge(channel)
        session.expunge(config)
        return channel, config


async def handle(channel_id: UUID, messages: list[providers.Inbound], limiter: Any = None) -> None:
    """Processa as mensagens de um webhook, uma de cada vez, na ordem em que chegaram."""
    loaded = await asyncio.to_thread(_load, channel_id)
    if loaded is None:
        return
    channel, config = loaded
    for msg in messages:
        saved = await asyncio.to_thread(_save_inbound, channel.id, channel.kind, msg)
        if saved is None:
            continue
        if limiter is not None:
            try:
                limiter.check(f"channel:{channel.id}:{msg.sender}", limit=PER_SENDER_LIMIT)
            except Exception:
                await asyncio.to_thread(_mark, saved.message_id, "ignored", "limite por minuto")
                continue
        if msg.text is None:
            await asyncio.to_thread(_mark, saved.message_id, "ignored", "não é texto")
            await asyncio.to_thread(
                deliver, channel, saved.conversation_id, msg.reply_to, ONLY_TEXT, "system"
            )
            continue
        if saved.status != "bot":
            # com uma pessoa atendendo, a mensagem só espera na fila de conversas
            continue
        if wants_human(channel, msg.text):
            if await asyncio.to_thread(handoff, saved.conversation_id, REASON_KEYWORD):
                await asyncio.to_thread(
                    deliver,
                    channel,
                    saved.conversation_id,
                    msg.reply_to,
                    channel.handoff_message,
                    "system",
                )
            continue
        await answer(channel, config, saved, msg.text, msg.reply_to)
