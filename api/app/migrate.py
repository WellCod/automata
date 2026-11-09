"""Migrações do boot num processo só: Alembic e depois as tabelas do Agno.

Antes eram dois interpretadores (`alembic upgrade head` e `python -m
app.agno_migrations`), cada um importando o app de novo, com o container limitado a
meia CPU (Fase 44). A ordem continua a mesma: as tabelas do Automata primeiro.

Uso: python -m app.migrate
"""

import logging

from alembic.config import Config

from alembic import command
from app.agno_migrations import migrate as migrate_agno
from app.logging_config import configure_logging
from app.settings import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging(get_settings().log_level)
    command.upgrade(Config("alembic.ini"), "head")
    migrate_agno()
    logger.info("banco na versão atual")


if __name__ == "__main__":
    main()
