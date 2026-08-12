import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check() -> JSONResponse:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"status": "ok"})
    except Exception as exc:
        logger.error("health check: db unreachable", extra={"error": str(exc)})
        return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)
