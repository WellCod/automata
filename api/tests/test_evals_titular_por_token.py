"""Evals do pedido do titular por token, pelo próprio usuário e do prazo (ADR-0036).

Sem banco. Errar o acesso é deixar um token de integração comum, ou um editor do
painel, exportar os dados de qualquer pessoa; ou impedir o owner de atender o pedido.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from app.integrations import integration_scopes
from app.models.user import UserRole
from app.routers.data_subjects import _is_admin, _source, require_subject_access
from app.schemas.user import ROLE_SCOPES


def _request(scopes: list[str], user_id: str = "u", enforce: bool = True) -> Any:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(enforce_scopes=enforce)),
        state=SimpleNamespace(scopes=scopes, admin_scope=None, user_id=user_id),
    )


TOKEN_COM = integration_scopes([], [], [], data_subjects=True)
TOKEN_SEM = integration_scopes([], [], [], data_subjects=False)


@pytest.mark.parametrize(
    ("name", "scopes", "allowed", "admin"),
    [
        ("owner", ROLE_SCOPES[UserRole.owner], True, True),
        ("editor", ROLE_SCOPES[UserRole.editor], False, False),
        ("viewer", ROLE_SCOPES[UserRole.viewer], False, False),
        ("token com a opção", TOKEN_COM, True, False),
        ("token sem a opção", TOKEN_SEM, False, False),
        ("token de agente", ["agents:x:run", "agents:x:read"], False, False),
    ],
)
def test_matriz_de_acesso(name: str, scopes: list[str], allowed: bool, admin: bool) -> None:
    request = _request(scopes)
    assert _is_admin(request) is admin, name
    if allowed:
        require_subject_access(request)
    else:
        with pytest.raises(HTTPException) as exc:
            require_subject_access(request)
        assert exc.value.status_code == 403, name


def test_app_sem_autenticacao_e_admin() -> None:
    assert _is_admin(_request([], enforce=False)) is True


def test_opcao_so_entra_quando_pedida() -> None:
    assert "data_subjects:request" in TOKEN_COM
    assert "data_subjects:request" not in TOKEN_SEM


@pytest.mark.parametrize(
    ("actor", "source"),
    [("integration:abc", "integration"), ("3f1c", "panel"), ("panel", "panel")],
)
def test_origem_pelo_ator(actor: str, source: str) -> None:
    assert _source(actor) == source


def test_prazo_pelo_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.data_subjects import due_date
    from app.settings import get_settings

    now = datetime(2026, 11, 4, 12, tzinfo=UTC)
    assert due_date(now) - now == timedelta(days=15)
    monkeypatch.setenv("DATA_SUBJECT_DEADLINE_DAYS", "10")
    get_settings.cache_clear()
    try:
        assert due_date(now) - now == timedelta(days=10)
    finally:
        monkeypatch.delenv("DATA_SUBJECT_DEADLINE_DAYS")
        get_settings.cache_clear()
