"""Recifra com a chave atual os segredos que ainda estão na anterior (ADR-0026).

Passa pelas quatro tabelas numa transação só. Valor que nenhuma chave decifra
interrompe tudo antes de gravar, com a tabela e o id. Rodar de novo não muda nada.

Uso: python -m app.rotate_secrets
"""

import logging
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.db import get_engine
from app.logging_config import configure_logging
from app.models.alert import AlertDestination
from app.models.eval import EvalSchedule
from app.models.knowledge_connector import KnowledgeConnector
from app.models.mcp_server import McpServer
from app.secrets import SecretsKeyMissing, on_current_key, reencrypt
from app.settings import get_settings

logger = logging.getLogger(__name__)

# tabela -> coluna cifrada; toda coluna nova cifrada com a chave dos segredos entra aqui
ENCRYPTED: dict[str, InstrumentedAttribute[Any]] = {
    "mcp_server": McpServer.headers_encrypted,
    "eval_schedule": EvalSchedule.webhook_encrypted,
    "alert_destination": AlertDestination.webhook_encrypted,
    "knowledge_connector": KnowledgeConnector.secret_encrypted,
}


class RotationError(RuntimeError):
    pass


def _rows(session: Session, column: InstrumentedAttribute[Any]) -> list[Any]:
    model = column.class_
    return list(session.scalars(select(model).where(column.is_not(None))))


def pending(session: Session) -> dict[str, int]:
    """Quantos segredos de cada tabela a chave atual ainda não abre."""
    counts: dict[str, int] = {}
    for table, column in ENCRYPTED.items():
        values = (getattr(row, column.key) for row in _rows(session, column))
        counts[table] = sum(1 for value in values if not on_current_key(value))
    return counts


def rotate_all(session: Session) -> dict[str, int]:
    """Recifra o que não está na chave atual; não faz commit."""
    changed: dict[str, int] = {}
    for table, column in ENCRYPTED.items():
        count = 0
        for row in _rows(session, column):
            value = getattr(row, column.key)
            if on_current_key(value):
                continue
            try:
                setattr(row, column.key, reencrypt(value))
            except SecretsKeyMissing as exc:
                raise RotationError(f"{table} {row.id}: nenhuma chave decifra o segredo") from exc
            count += 1
        changed[table] = count
    return changed


def main() -> int:
    configure_logging(get_settings().log_level)
    with Session(get_engine()) as session:
        try:
            changed = rotate_all(session)
        except (RotationError, SecretsKeyMissing) as exc:
            session.rollback()
            logger.error("rotação dos segredos interrompida, nada foi gravado: %s", exc)
            return 1
        session.commit()
    for table, count in changed.items():
        logger.info("segredos recifrados", extra={"table": table, "count": count})
    return 0


if __name__ == "__main__":
    sys.exit(main())
