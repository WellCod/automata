import logging
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Connection, text

from app.db import get_engine

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)

# rodada do poller de avisos mais velha que isso: o laço morreu ou travou (OPS-05)
POLLER_STALE_S = 600


def _redis(request: Request) -> str:
    """Estado do Redis do limitador de chamadas; "off" quando a instância roda sem ele."""
    limiter = getattr(request.app.state, "rate_limiter", None)
    return str(limiter.state()) if limiter is not None else "off"


def _migration(connection: Connection) -> str | None:
    """Revisão do Alembic aplicada no banco, ou None sem a tabela.

    O savepoint isola a falha: sem ele, a consulta errada invalidaria a conexão do health.
    """
    try:
        with connection.begin_nested():
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception:
        return None
    return None if revision is None else str(revision)


@router.get("/health")
def health_check(request: Request) -> JSONResponse:
    """Estado da instância para o monitor externo (via `/api/health` do painel).

    503 só com o banco fora; Redis fora ou poller parado deixam `degraded` com 200,
    porque a API segue atendendo.
    """
    from app.alerts import last_cycle_age

    body: dict[str, object] = {
        "status": "ok",
        # da imagem publicada (build-arg no publish.yml); "dev" no build local
        "version": os.environ.get("AUTOMATA_VERSION", "dev"),
        "revision": os.environ.get("AUTOMATA_REVISION", ""),
    }
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            body["migration"] = _migration(connection)
    except Exception as exc:
        logger.error("health check: db unreachable", extra={"error": str(exc)})
        return JSONResponse({**body, "status": "degraded", "db": "unreachable"}, status_code=503)
    body["db"] = "ok"
    body["redis"] = _redis(request)
    poller_age_s = last_cycle_age(time.monotonic())
    body["poller_age_s"] = None if poller_age_s is None else round(poller_age_s)
    if body["redis"] == "unreachable" or (
        poller_age_s is not None and poller_age_s > POLLER_STALE_S
    ):
        body["status"] = "degraded"
    return JSONResponse(body)
