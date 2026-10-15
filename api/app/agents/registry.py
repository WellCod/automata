"""Mantém os agentes publicados registrados no AgentOS sem restart.

O AgentOS lê `os.agents` a cada request, mas só montava a lista no boot:
config publicado depois disso não respondia até reiniciar. A sincronização
roda logo após publicar (mesmo processo) e, com TTL, antes de requests ao
runtime — o que cobre publicações feitas por outros workers.
"""

import logging
import threading
from collections.abc import Callable
from time import monotonic
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models.config import AgentConfig

logger = logging.getLogger(__name__)


def published_config_ids() -> list[UUID]:
    with Session(get_engine()) as session:
        stmt = select(AgentConfig.id).where(AgentConfig.current_version_id.is_not(None))
        return list(session.scalars(stmt))


class PublishedAgents:
    def __init__(
        self,
        entries: list[Any],
        make_factory: Callable[[UUID], Any],
        *,
        ttl_seconds: float = 5.0,
        load_ids: Callable[[], list[UUID]] = published_config_ids,
    ) -> None:
        # `entries` é a mesma lista passada ao AgentOS: mutada no lugar
        self._entries = entries
        self._make_factory = make_factory
        self._ttl = ttl_seconds
        self._load_ids = load_ids
        self._lock = threading.Lock()
        self._synced_at: float | None = None

    @property
    def entries(self) -> list[Any]:
        return self._entries

    def sync(self) -> int:
        """Registra factories de configs publicados que ainda não estão na lista."""
        try:
            ids = self._load_ids()
        except Exception as exc:
            logger.warning("falha ao sincronizar agentes", extra={"error": str(exc)})
            return 0
        with self._lock:
            known = {str(e.id) for e in self._entries}
            added = [self._make_factory(i) for i in ids if str(i) not in known]
            self._entries.extend(added)
            self._synced_at = monotonic()
        if added:
            logger.info("agentes registrados", extra={"count": len(added)})
        return len(added)

    def is_stale(self) -> bool:
        return self._synced_at is None or monotonic() - self._synced_at >= self._ttl
