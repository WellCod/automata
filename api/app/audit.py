"""Trilha de auditoria (ADR-0041): quem mudou o quê, quando, de onde e com que resultado.

O middleware fica no app externo e grava depois da resposta toda escrita em `/api/v1`
e o `continue` das aprovações. O corpo nunca entra: tem prompt, segredo e dado pessoal.
As rotas que mudam produção põem o antes e o depois com `note`.
"""

import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import Request, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.db import get_engine
from app.logging_config import request_id_var
from app.models.audit import AuditEvent
from app.proxy import get_client_ip

logger = logging.getLogger(__name__)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# login e logout sem autor antes de autenticar; o linter só lê. Criar usuário em
# /api/v1/auth/users entra (Fase 49)
_SKIP_PREFIXES = (
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/oidc",
    "/api/v1/linter",
    # servidor MCP: cada chamada de tool é um POST, já registrado como run
    "/mcp",
    # mensagem que chega por canal (ADR-0044): já fica em channel_message
    "/hooks/",
)
# conversa não é ação de administração: já está em agent_run, com quem chamou
_RUN = re.compile(r"^/(agents|teams|workflows)/[^/]+/runs/?$")
# POST que só lê
_READ_SUFFIXES = ("/search", "/search/compare", "/chunk-preview")
_CONTINUE = re.compile(r"^/(agents|teams|workflows)/[^/]+/runs/[^/]+/continue$")
_WEBHOOK = re.compile(r"^/api/v1/knowledge-connectors/[^/]+/webhook$")
# id de titular no path: entra já como pseudônimo, para a exclusão não correr atrás dele
_SUBJECT_ROUTE = "/data-subjects/{user_id}"

DEFAULT_RETENTION_DAYS = 365


def should_audit(method: str, path: str) -> bool:
    """Toda escrita, inclusive as rotas nativas do AgentOS (aprovações, sessões,
    memórias, agendamentos), menos conversa, login e o que só lê (Fase 49)."""
    if method not in WRITE_METHODS:
        return False
    if _CONTINUE.match(path):
        return True
    if path.startswith(_SKIP_PREFIXES) or _RUN.match(path):
        return False
    if method == "POST" and _WEBHOOK.match(path):
        return False
    return not (method == "POST" and path.endswith(_READ_SUFFIXES))


# service accounts do AgentOS cunham token admin sem validade, fora das integrações,
# da rotação de chaves e da trilha (Fase 49); o painel usa tokens de integração
BLOCKED_PREFIXES = ("/service-accounts",)


def note(request: Request, **detail: Any) -> None:
    """Antes e depois da ação, lido pelo middleware depois da resposta."""
    current: dict[str, Any] = getattr(request.state, "audit_detail", None) or {}
    current.update(detail)
    request.state.audit_detail = current


def _jsonable(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def record(
    *,
    actor: str | None,
    action: str,
    params: dict[str, str],
    status_code: int,
    ip: str | None,
    request_id: str | None,
    detail: dict[str, Any] | None,
) -> None:
    config_id: UUID | None = None
    raw = params.pop("config_id", None)
    if raw:
        try:
            config_id = UUID(raw)
        except ValueError:
            params["config_id"] = raw
    if _SUBJECT_ROUTE in action and "user_id" in params:
        from app.data_subjects import pseudonym

        params["user_id"] = pseudonym(params["user_id"])
    with Session(get_engine()) as session:
        session.add(
            AuditEvent(
                actor=actor,
                action=action[:255],
                config_id=config_id,
                params=params or None,
                status_code=status_code,
                ip=(ip or "")[:64] or None,
                request_id=(request_id or "")[:64] or None,
                detail=_jsonable(detail) if detail else None,
            )
        )
        session.commit()


def _route_words(app: Any) -> frozenset[str]:
    """Segmentos fixos de todas as rotas do app, inclusive as do AgentOS montado. Sem
    cache: o AgentOS registra rotas no lifespan, e isto só roda em escrita sem rota casada."""
    words: set[str] = set()
    pending = list(getattr(getattr(app, "router", app), "routes", []))
    while pending:
        route = pending.pop()
        context = getattr(route, "include_context", None)
        fixed = [str(getattr(route, "path", "")), str(getattr(context, "prefix", ""))]
        for part in "/".join(fixed).split("/"):
            if part and "{" not in part:
                words.add(part)
        # o FastAPI guarda router incluído como _IncludedRouter, com as rotas no original
        original = getattr(route, "original_router", None)
        if original is not None:
            pending.extend(getattr(original, "routes", []))
        inner = getattr(route, "app", None)
        if inner is not None and inner is not app:
            pending.extend(getattr(getattr(inner, "router", inner), "routes", []))
    return frozenset(words)


def masked_path(app: Any, path: str) -> str:
    words = _route_words(app)
    parts = [p if p in words else "*" for p in path.split("/")[1:]]
    return "/" + "/".join(parts)


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        path = request.url.path
        if path.startswith(BLOCKED_PREFIXES):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        try:
            response: Response = await call_next(request)  # type: ignore[operator]
        except Exception:
            # a escrita pode ter gravado antes de estourar: registra o 500 e relança
            if should_audit(request.method, path):
                await self._record(request, 500, path)
            raise
        if should_audit(request.method, path):
            await self._record(request, response.status_code, path)
        return response

    async def _record(self, request: Request, status_code: int, path: str) -> None:
        route = request.scope.get("route")
        template = getattr(route, "path", None)
        # sem rota casada (401 antes do roteamento, 404, 405) o path cru levaria o id do
        # titular em claro para a trilha, onde a exclusão não alcança: só ficam as palavras
        # das rotas registradas (Fase 49)
        params = (
            {str(k): str(v) for k, v in (request.scope.get("path_params") or {}).items()}
            if template
            else {}
        )
        actor = getattr(request.state, "user_id", None)
        try:
            await run_in_threadpool(
                record,
                actor=str(actor) if actor else None,
                action=f"{request.method} {template or masked_path(request.app, path)}",
                params=params,
                status_code=status_code,
                ip=get_client_ip(request),
                request_id=request_id_var.get(None),
                detail=getattr(request.state, "audit_detail", None),
            )
        except Exception as exc:
            # a trilha nunca derruba a ação que ela registra
            logger.error("falha ao gravar auditoria", extra={"path": path, "error": str(exc)})


def purge(session: Session, now: datetime, days: int | None = None) -> int:
    """Apaga o que passou da retenção. Roda na rodada do poller."""
    if days is None:
        from app.settings import get_settings

        days = get_settings().audit_retention_days
    result = session.execute(
        delete(AuditEvent).where(AuditEvent.created_at < now - timedelta(days=days))
    )
    session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


_last_purge: date | None = None


def purge_daily(session: Session, now: datetime) -> int:
    """Uma vez por dia em cada processo; o DELETE é idempotente entre réplicas."""
    global _last_purge
    if _last_purge == now.date():
        return 0
    _last_purge = now.date()
    return purge(session, now)


def forget_subject(session: Session, user_id: str, alias: str) -> int:
    """Exclusão do titular (ADR-0032): o id dele vira o pseudônimo como autor e como alvo,
    e o IP das ações dele sai (Fase 49)."""
    by_actor = session.execute(
        update(AuditEvent).where(AuditEvent.actor == user_id).values(actor=alias, ip=None)
    )
    as_subject = session.execute(
        update(AuditEvent)
        .where(AuditEvent.params["subject"].astext == user_id)
        .values(params=AuditEvent.params.op("||")(func.jsonb_build_object("subject", alias)))
    )
    as_target = session.execute(
        update(AuditEvent)
        .where(AuditEvent.params["user_id"].astext == user_id)
        .values(params=AuditEvent.params.op("||")(func.jsonb_build_object("user_id", alias)))
    )
    return sum(int(getattr(r, "rowcount", 0) or 0) for r in (by_actor, as_target, as_subject))


def page(
    session: Session,
    *,
    actor: str | None,
    config_id: UUID | None,
    action: str | None,
    since: datetime | None,
    until: datetime | None,
    before: tuple[datetime, UUID] | None,
    limit: int,
) -> list[AuditEvent]:
    query = select(AuditEvent)
    if actor:
        query = query.where(AuditEvent.actor == actor)
    if config_id:
        query = query.where(AuditEvent.config_id == config_id)
    if action:
        query = query.where(AuditEvent.action.ilike(f"%{_escape(action)}%", escape="\\"))
    if since:
        query = query.where(AuditEvent.created_at >= since)
    if until:
        query = query.where(AuditEvent.created_at < until)
    if before:
        at, event_id = before
        query = query.where(
            (AuditEvent.created_at < at)
            | ((AuditEvent.created_at == at) & (AuditEvent.id < event_id))
        )
    query = query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit)
    return list(session.scalars(query))


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def now() -> datetime:
    return datetime.now(UTC)
