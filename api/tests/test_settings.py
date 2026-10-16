import pytest
from pydantic import ValidationError

from app.settings import Settings, get_settings


def test_settings_falha_sem_vars_obrigatorias(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("DATABASE_URL", "JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY"):
        monkeypatch.delenv(var, raising=False)
    # sem isso o api/.env da máquina preenche as variáveis e o teste passa a depender dela
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_settings_carrega_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()

    s = get_settings()
    assert s.database_url == "postgresql+psycopg://u:p@localhost/db"

    get_settings.cache_clear()


def test_extensoes_de_conhecimento_normalizadas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    monkeypatch.setenv("KNOWLEDGE_ALLOWED_EXTENSIONS", " PDF, .md,,txt ")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.knowledge_extensions == frozenset({"pdf", "md", "txt"})
    assert s.knowledge_default_embedder == "voyage"


def test_embedder_desconhecido_e_recusado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    monkeypatch.setenv("KNOWLEDGE_DEFAULT_EMBEDDER", "anthropic")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
