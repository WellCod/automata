import pytest
from pydantic import ValidationError

from app.settings import Settings, get_settings


def test_settings_falha_sem_vars_obrigatorias() -> None:
    with pytest.raises(ValidationError):
        Settings()


def test_settings_carrega_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()

    s = get_settings()
    assert s.database_url == "postgresql+psycopg://u:p@localhost/db"

    get_settings.cache_clear()
