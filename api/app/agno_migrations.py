"""Migração das tabelas do Agno, rodada no entrypoint depois do alembic.

O Alembic cuida só das tabelas do Automata. As do Agno (sessões, runs, evals,
métricas) têm versão de schema própria, e a v3 exige o `MigrationManager` antes de
servir tráfego: os runs saem do JSON da sessão para `agno_runs` e várias tabelas
ganham `user_id`. A migração é idempotente e não apaga nada; a coluna antiga
`runs` fica como backup. Limpar essa coluna (`cleanup_legacy_runs_column`) é
decisão manual de quem opera, nunca do boot.

Uso: python -m app.agno_migrations
"""

import asyncio
import logging

from agno.db.migrations.manager import MigrationManager

from app.db import get_db
from app.logging_config import configure_logging
from app.settings import get_settings

logger = logging.getLogger(__name__)


def migrate() -> None:
    asyncio.run(MigrationManager(get_db()).up())


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    migrate()
    logger.info("tabelas do agno na versão atual")
