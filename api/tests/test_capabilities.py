"""Testes da matriz de capabilities e do endpoint GET /api/v1/models/capabilities."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.agents.capabilities import get_capabilities, validate_capabilities
from app.schemas.config import CapabilityFlags
from app.settings import get_settings


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- capabilities matrix ---


def test_claude_sonnet_suporta_extended_thinking() -> None:
    caps = get_capabilities("claude-sonnet-4-6")
    assert caps.extended_thinking is True


def test_claude_haiku_nao_suporta_extended_thinking() -> None:
    caps = get_capabilities("claude-haiku-4-5")
    assert caps.extended_thinking is False


def test_o3_nao_suporta_vision() -> None:
    caps = get_capabilities("o3")
    assert caps.vision is False


def test_get_capabilities_modelo_desconhecido() -> None:
    with pytest.raises(ValueError, match="não suportado"):
        get_capabilities("modelo-fake")


# --- validate_capabilities ---


def test_validate_sem_erros() -> None:
    flags = CapabilityFlags(extended_thinking=True, vision=True)
    errors = validate_capabilities("claude-sonnet-4-6", flags)
    assert errors == []


def test_validate_extended_thinking_nao_suportado() -> None:
    flags = CapabilityFlags(extended_thinking=True)
    errors = validate_capabilities("claude-haiku-4-5", flags)
    assert any("extended_thinking" in e for e in errors)


def test_validate_vision_nao_suportado() -> None:
    flags = CapabilityFlags(vision=True)
    errors = validate_capabilities("o3", flags)
    assert any("vision" in e for e in errors)


def test_validate_flags_desativadas_sao_sempre_validas() -> None:
    flags = CapabilityFlags()
    errors = validate_capabilities("o3-mini", flags)
    assert errors == []


# --- endpoint ---


def test_endpoint_capabilities() -> None:
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False))
    response = client.get("/api/v1/models/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "claude-sonnet-4-6" in data
    assert "gpt-4o" in data
    assert isinstance(data["claude-sonnet-4-6"]["extended_thinking"], bool)


def test_endpoint_capabilities_contem_todos_modelos() -> None:
    from app.agents.capabilities import all_capabilities
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False))
    response = client.get("/api/v1/models/capabilities")
    assert response.status_code == 200
    assert set(response.json().keys()) == set(all_capabilities().keys())
