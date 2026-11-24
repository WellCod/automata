"""Migrações do boot num processo só: Alembic e depois as tabelas do Agno.

Antes eram dois interpretadores (`alembic upgrade head` e `python -m
app.agno_migrations`), cada um importando o app de novo, com o container limitado a
meia CPU (Fase 44). A ordem continua a mesma: as tabelas do Automata primeiro.

Uso: python -m app.migrate
"""

import logging
import sys

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from alembic import command
from app.agno_migrations import migrate as migrate_agno
from app.db import get_engine
from app.logging_config import configure_logging
from app.settings import get_settings

logger = logging.getLogger(__name__)

# duas réplicas subindo juntas não migram ao mesmo tempo (OPS-10)
_LOCK_KEY = 7_340_051


def _ahead(config: Config) -> str | None:
    """Revisão do banco que esta imagem não conhece: o banco veio de uma imagem mais nova."""
    script = ScriptDirectory.from_config(config)
    with get_engine().connect() as connection:
        try:
            db_revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        except Exception:
            # banco novo, ainda sem a tabela do Alembic: nada à frente
            return None
    if db_revision is None:
        return None
    try:
        script.get_revision(db_revision)
    except Exception:
        return str(db_revision)
    return None


def main() -> None:
    """Recusa subir com banco de imagem mais nova; senão migra Automata e Agno sob lock."""
    configure_logging(get_settings().log_level)
    config = Config("alembic.ini")
    unknown_revision = _ahead(config)
    if unknown_revision is not None:
        head = ScriptDirectory.from_config(config).get_current_head()
        logger.error(
            "banco numa migration que esta imagem não conhece: volte para a imagem nova ou"
            " rode o downgrade com ela antes (docs/atualizacao.md)",
            extra={"db": unknown_revision, "image_head": head},
        )
        sys.exit(1)
    # autocommit: transação aberta nesta conexão travaria o CREATE INDEX CONCURRENTLY da
    # 0052, que espera todas as transações em curso terminarem (achado do smoke do compose)
    lock_connection = get_engine().connect().execution_options(isolation_level="AUTOCOMMIT")
    with lock_connection:
        lock_connection.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _LOCK_KEY})
        try:
            command.upgrade(config, "head")
            migrate_agno()
        finally:
            lock_connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
    logger.info("banco na versão atual")


if __name__ == "__main__":
    main()
