"""Conversas dos canais nos pedidos do titular (ADR-0032, ADR-0044).

O `user_id` da conversa é `whatsapp:<número>` ou `slack:<usuário>`, o mesmo dos runs.
"""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.channel import ChannelConversation, ChannelMessage


def count(session: Session, user_id: str) -> int:
    return int(
        session.scalar(
            select(func.count(ChannelMessage.id))
            .join(ChannelConversation, ChannelConversation.id == ChannelMessage.conversation_id)
            .where(ChannelConversation.user_id == user_id)
        )
        or 0
    )


def export(session: Session, user_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    conversations = session.scalars(
        select(ChannelConversation).where(ChannelConversation.user_id == user_id)
    )
    for conv in conversations:
        messages = session.scalars(
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conv.id)
            .order_by(ChannelMessage.created_at)
        )
        out.append(
            {
                "conversation_id": str(conv.id),
                "channel_id": str(conv.channel_id),
                "status": conv.status,
                "created_at": conv.created_at.isoformat(),
                "messages": [
                    {
                        "direction": m.direction,
                        "author": m.author,
                        "text": m.text,
                        "status": m.status,
                        "created_at": m.created_at.isoformat(),
                    }
                    for m in messages
                ],
            }
        )
    return out


def erase(session: Session, user_id: str) -> int:
    """Apaga as conversas do titular; as mensagens saem em cascata."""
    result = session.execute(
        delete(ChannelConversation).where(ChannelConversation.user_id == user_id)
    )
    return int(getattr(result, "rowcount", 0) or 0)
