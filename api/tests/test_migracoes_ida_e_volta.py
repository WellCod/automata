"""Migrations sobem e descem inteiras, e a imagem velha não migra banco novo (OPS-10).

Antes nenhum teste rodava o `downgrade` das 58 migrations, e voltar a imagem com o banco
numa revisão desconhecida deixava o container em laço de restart sem explicar o porquê.
"""

from collections.abc import Generator

import pytest
from alembic.config import Config
from sqlalchemy import text
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings


@pytest.fixture(scope="module")
def db(monkeypatch_module: pytest.MonkeyPatch) -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        monkeypatch_module.setenv("DATABASE_URL", url)
        monkeypatch_module.setenv("JWT_PRIVATE_KEY", "x")
        monkeypatch_module.setenv("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        yield url
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def monkeypatch_module() -> Generator[pytest.MonkeyPatch, None, None]:
    patch = pytest.MonkeyPatch()
    yield patch
    patch.undo()


def _version() -> str | None:
    from app.db import get_engine

    with get_engine().connect() as conn:
        value = conn.scalar(text("SELECT version_num FROM alembic_version"))
    return None if value is None else str(value)


def test_downgrade_ate_a_base_e_upgrade_de_novo(db: str) -> None:
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    head = _version()
    command.downgrade(config, "base")
    assert _version() is None
    command.upgrade(config, "head")
    assert _version() == head


def test_imagem_velha_nao_migra_banco_novo(db: str) -> None:
    from app import migrate
    from app.db import get_engine

    command.upgrade(Config("alembic.ini"), "head")
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num = '9999'"))
    with pytest.raises(SystemExit) as exc:
        migrate.main()
    assert exc.value.code == 1
    assert _version() == "9999"
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM alembic_version"))
    command.stamp(Config("alembic.ini"), "head")


def test_migracao_do_boot_com_lock_passa_pelo_indice_concorrente(db: str) -> None:
    """A 0052 cria índice com CONCURRENTLY: com o lock numa transação aberta, travava."""
    import threading

    from app import migrate

    command.downgrade(Config("alembic.ini"), "0051")
    done = threading.Event()
    worker = threading.Thread(target=lambda: (migrate.main(), done.set()), daemon=True)
    worker.start()
    assert done.wait(120), "migração do boot travou"
    assert _version() is not None and _version() >= "0052"
