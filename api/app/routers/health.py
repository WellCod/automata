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
    limiter = getattr(request.app.state, "rate_limiter", None)
    return str(limiter.state()) if limiter is not None else "off"


def _migration(conn: Connection) -> str | None:
    try:
        with conn.begin_nested():
            value = conn.scalar(text("SELECT version_num FROM alembic_version"))
    except Exception:
        return None
    return None if value is None else str(value)


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
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
            body["migration"] = _migration(conn)
    except Exception as exc:
        logger.error("health check: db unreachable", extra={"error": str(exc)})
        return JSONResponse({**body, "status": "degraded", "db": "unreachable"}, status_code=503)
    body["db"] = "ok"
    body["redis"] = _redis(request)
    age = last_cycle_age(time.monotonic())
    body["poller_age_s"] = None if age is None else round(age)
    if body["redis"] == "unreachable" or (age is not None and age > POLLER_STALE_S):
        body["status"] = "degraded"
    return JSONResponse(body)
