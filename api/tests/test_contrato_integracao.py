"""Formato das rotas que o token de integração alcança, congelado (ARQ-05).

As rotas de run são do AgentOS e mudam com o upgrade do Agno. Campo novo é aceito (o
teste lista os obrigatórios de hoje); campo que some ou muda de nome quebra o integrador
e precisa sair nas notas da versão e em docs/api-integracao.md.
"""

from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings

# rota → campos do formulário que o docs/api-integracao.md documenta
CONTRACT = {
    ("POST", "/agents/{agent_id}/runs"): {"message", "stream", "session_id", "factory_input"},
    ("POST", "/teams/{team_id}/runs"): {"message", "stream", "session_id", "factory_input"},
    ("POST", "/workflows/{workflow_id}/runs"): {"message", "stream", "session_id"},
    ("POST", "/agents/{agent_id}/runs/{run_id}/continue"): {"tools", "session_id", "stream"},
}


@pytest.fixture(scope="module")
def app() -> Generator[Any, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        patch = pytest.MonkeyPatch()
        patch.setenv("DATABASE_URL", pg.get_connection_url().replace("psycopg2", "psycopg"))
        patch.setenv("JWT_PRIVATE_KEY", "x")
        patch.setenv("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        from app.main import create_app

        yield create_app(auto_provision_dbs=False, enable_auth=False, enable_mcp_server=False)
        patch.undo()
        get_settings.cache_clear()


def _routes(app: Any) -> dict[tuple[str, str], set[str]]:
    """Rotas com o prefixo completo; o FastAPI guarda router incluído como _IncludedRouter."""
    from fastapi.routing import APIRoute

    found: dict[tuple[str, str], set[str]] = {}
    pending: list[tuple[Any, str]] = [(r, "") for r in app.router.routes]
    while pending:
        route, prefix = pending.pop()
        context = getattr(route, "include_context", None)
        here = prefix + str(getattr(context, "prefix", "") or "")
        original = getattr(route, "original_router", None)
        if original is not None:
            pending.extend((r, here) for r in original.routes)
            continue
        if isinstance(route, APIRoute):
            fields = {p.alias for p in route.dependant.body_params}
            for method in route.methods:
                found[(method, prefix + route.path)] = fields
            continue
        inner = getattr(route, "app", None)
        if inner is not None and inner is not app:
            mount = prefix + str(getattr(route, "path", "") or "")
            pending.extend(
                (r, mount) for r in getattr(getattr(inner, "router", inner), "routes", [])
            )
    return found


def test_rotas_de_integracao_mantem_os_campos_documentados(app: Any) -> None:
    from fastapi.testclient import TestClient

    # o AgentOS registra as rotas de run no lifespan
    with TestClient(app):
        routes = _routes(app)
    for key, fields in CONTRACT.items():
        assert key in routes, f"rota sumiu: {key}"
        missing = fields - routes[key]
        assert not missing, f"{key} perdeu {missing}"
