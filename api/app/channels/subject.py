"""Conversas dos canais nos pedidos do titular (ADR-0032, ADR-0044).

O `user_id` da conversa é `whatsapp:<número>` ou `slack:<usuário>`, o mesmo dos runs.
"""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.channel import ChannelConversation, ChannelMessage


def count(session: Session, user_id: str) -> int:
    """Mensagens de canal guardadas do titular."""
    return int(
        session.scalar(
            select(func.count(ChannelMessage.id))
            .join(ChannelConversation, ChannelConversation.id == ChannelMessage.conversation_id)
            .where(ChannelConversation.user_id == user_id)
        )
        or 0
    )


def export(session: Session, user_id: str) -> list[dict[str, Any]]:
    """Conversas do titular com as mensagens em ordem, para o arquivo de exportação."""
    exported: list[dict[str, Any]] = []
    conversations = session.scalars(
        select(ChannelConversation).where(ChannelConversation.user_id == user_id)
    )
    for conversation in conversations:
        messages = session.scalars(
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conversation.id)
            .order_by(ChannelMessage.created_at)
        )
        exported.append(
            {
                "conversation_id": str(conversation.id),
                "channel_id": str(conversation.channel_id),
                "status": conversation.status,
                "created_at": conversation.created_at.isoformat(),
                "messages": [
                    {
                        "direction": message.direction,
                        "author": message.author,
                        "text": message.text,
                        "status": message.status,
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in messages
                ],
            }
        )
    return exported


def erase(session: Session, user_id: str) -> int:
    """Apaga as conversas do titular; as mensagens saem em cascata."""
    result = session.execute(
        delete(ChannelConversation).where(ChannelConversation.user_id == user_id)
    )
    return int(getattr(result, "rowcount", 0) or 0)
