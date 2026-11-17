"""Toda escrita própria exige scope (ARQ-03).

Cada router declara o próprio scope; nada impedia uma rota nova sem dependência de
`app.authz` de ficar aberta a qualquer token válido. As exceções ficam listadas aqui,
com o porquê.
"""

from typing import Any

from fastapi.routing import APIRoute

from app.routers import PROTECTED_ROUTERS

# rotas da própria pessoa: qualquer token de usuário vale e a rota confere o dono
EXCEPTIONS = {
    ("POST", "/api/v1/me/password"),
    ("DELETE", "/api/v1/me/memories/{memory_id}"),
    ("DELETE", "/api/v1/me/memories"),
    # lint é leitura com corpo: não grava nada
    ("POST", "/api/v1/lint"),
    # titular: a rota decide entre owner, token pelo próprio id e o próprio usuário
    # (`_is_admin`, `_own_subject`, ADR-0036), com teste próprio em test_data_subjects
    ("POST", "/api/v1/data-subjects/{user_id}/export"),
    ("POST", "/api/v1/data-subjects/{user_id}/erase"),
    ("POST", "/api/v1/me/data/export"),
    ("POST", "/api/v1/me/data/erase"),
}


def _guarded(dependant: Any) -> bool:
    for dep in dependant.dependencies:
        call = dep.call
        if getattr(call, "__module__", "") == "app.authz":
            return True
        if _guarded(dep):
            return True
    return False


def _routes() -> list[tuple[str, str, bool]]:
    out = []
    for router in PROTECTED_ROUTERS:
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods - {"GET", "HEAD", "OPTIONS"}:
                out.append((method, route.path, _guarded(route.dependant)))
    return out


def test_toda_escrita_tem_scope_ou_esta_na_lista_de_excecoes() -> None:
    routes = _routes()
    assert len(routes) > 50
    open_routes = {(m, p) for m, p, guarded in routes if not guarded}
    assert open_routes - EXCEPTIONS == set()


def test_flag_ausente_confere_scope() -> None:
    from types import SimpleNamespace

    from app.authz import scopes_enforced

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    assert scopes_enforced(request) is True  # type: ignore[arg-type]
