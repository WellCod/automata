"""Mantém agentes e times publicados registrados no AgentOS sem restart.

O AgentOS lê `os.agents` e `os.teams` a cada request, mas só montava as
listas no boot: config publicado depois disso não respondia até reiniciar. A
sincronização roda logo após publicar (mesmo processo) e, com TTL, antes de
requests ao runtime — o que cobre publicações feitas por outros workers.
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


def published_configs() -> list[tuple[UUID, str]]:
    """(id, kind) dos configs com versão vigente."""
    with Session(get_engine()) as session:
        stmt = select(AgentConfig.id, AgentConfig.kind).where(
            AgentConfig.current_version_id.is_not(None)
        )
        return [(row.id, row.kind) for row in session.execute(stmt)]


class PublishedAgents:
    def __init__(
        self,
        entries: list[Any],
        make_factory: Callable[[UUID], Any],
        *,
        teams: list[Any] | None = None,
        make_team_factory: Callable[[UUID], Any] | None = None,
        ttl_seconds: float = 5.0,
        load: Callable[[], list[tuple[UUID, str]]] = published_configs,
    ) -> None:
        # Listas passadas ao AgentOS (agents=, teams=): mutadas no lugar
        self._entries = entries
        self._teams = teams if teams is not None else []
        self._make_factory = make_factory
        self._make_team_factory = make_team_factory
        self._ttl = ttl_seconds
        self._load = load
        self._lock = threading.Lock()
        self._synced_at: float | None = None

    @property
    def entries(self) -> list[Any]:
        return self._entries

    @property
    def teams(self) -> list[Any]:
        return self._teams

    def sync(self) -> int:
        """Registra factories de configs publicados que ainda não estão nas listas."""
        try:
            published = self._load()
        except Exception as exc:
            # tenta de novo só após o TTL, para banco fora do ar não atrasar toda request
            logger.warning("falha ao sincronizar agentes", extra={"error": str(exc)})
            with self._lock:
                self._synced_at = monotonic()
            return 0
        added = 0
        with self._lock:
            known = {str(e.id) for e in [*self._entries, *self._teams]}
            for config_id, kind in published:
                if str(config_id) in known:
                    continue
                if kind == "team":
                    if self._make_team_factory is None:
                        continue
                    self._teams.append(self._make_team_factory(config_id))
                else:
                    self._entries.append(self._make_factory(config_id))
                added += 1
            self._synced_at = monotonic()
        if added:
            logger.info("componentes registrados", extra={"count": added})
        return added

    def is_stale(self) -> bool:
        return self._synced_at is None or monotonic() - self._synced_at >= self._ttl
