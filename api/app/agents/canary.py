"""Liberação gradual de versão (ADR-0040): qual versão responde a uma conversa.

A escolha é pela sessão, para a conversa não trocar de prompt e de modelo no meio.
Sem sessão, o sorteio é por run.
"""

import hashlib
import secrets
from uuid import UUID

# acima disso o canário deixa de ser a minoria das conversas: aí é publicar
MAX_PERCENT = 50


def bucket(config_id: UUID, session_id: str | None) -> int:
    """De 0 a 99, estável para a mesma conversa do mesmo config."""
    if not session_id:
        return secrets.randbelow(100)
    digest = hashlib.sha256(f"{config_id}:{session_id}".encode()).hexdigest()
    return int(digest[:8], 16) % 100


def in_canary(config_id: UUID, session_id: str | None, percent: int | None) -> bool:
    """Se a conversa cai na versão canário, com o percentual limitado a `MAX_PERCENT`."""
    if not percent:
        return False
    return bucket(config_id, session_id) < min(percent, MAX_PERCENT)
