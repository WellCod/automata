"""Testes de invariantes do ConfigService.

Invariante 1: publish cria uma nova linha, nunca atualiza versão publicada.
Invariante 2: rollback só move o ponteiro, não altera dados de versão.
Invariante 3: descrição é obrigatória e com conteúdo (min_length=1).
Invariante 4: alterar descrição de agente publicado cria novo rascunho.
"""

import os
from collections.abc import Generator

import pytest
from alembic.config import Config
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.repositories.config import ConfigRepository
from app.schemas.config import ConfigPayload, ConfigPayloadStatus, CreateConfigInput, DraftInput
from app.services.config import ConfigService


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("postgres:17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        yield url
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def session(db_url: str) -> Generator[Session, None, None]:
    engine = create_engine(db_url)
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(bind=conn) as sess:
            yield sess
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def payload() -> ConfigPayload:
    return ConfigPayload(model_id="gpt-4o")


def test_publish_cria_nova_versao_nao_atualiza_rascunho(
    session: Session, payload: ConfigPayload
) -> None:
    repo = ConfigRepository(session)
    svc = ConfigService(repo)

    config = svc.create_config("agente-teste", description="Agente de teste")
    draft = svc.save_draft(config.id, payload, "autor")
    draft_id = draft.id

    published = svc.publish(config.id, "autor")

    # versão publicada é uma linha nova
    assert published.id != draft_id
    assert published.status == ConfigPayloadStatus.published

    # rascunho original permanece intacto
    draft_after = repo.get_version(draft_id)
    assert draft_after is not None
    assert draft_after.status == ConfigPayloadStatus.draft
    assert draft_after.id == draft_id

    # ponteiro atualizado
    config_after = repo.get_config(config.id)
    assert config_after is not None
    assert config_after.current_version_id == published.id
    assert config_after.draft_version_id is None


def test_rollback_so_move_ponteiro(session: Session, payload: ConfigPayload) -> None:
    repo = ConfigRepository(session)
    svc = ConfigService(repo)

    config = svc.create_config("agente-rollback", description="Agente de rollback")

    svc.save_draft(config.id, payload, "autor")
    v1 = svc.publish(config.id, "autor")
    v1_payload_antes = dict(v1.payload)
    v1_number_antes = v1.version_number

    svc.save_draft(config.id, ConfigPayload(model_id="claude-sonnet-4-6"), "autor")
    v2 = svc.publish(config.id, "autor")

    config_mid = repo.get_config(config.id)
    assert config_mid is not None
    assert config_mid.current_version_id == v2.id

    svc.rollback(config.id, v1.id)

    # ponteiro voltou para v1
    config_after = repo.get_config(config.id)
    assert config_after is not None
    assert config_after.current_version_id == v1.id

    # dados de v1 não foram alterados
    v1_after = repo.get_version(v1.id)
    assert v1_after is not None
    assert v1_after.payload == v1_payload_antes
    assert v1_after.version_number == v1_number_antes

    # v2 também intacto
    v2_after = repo.get_version(v2.id)
    assert v2_after is not None
    assert v2_after.status == ConfigPayloadStatus.published


def test_descricao_em_branco_invalida() -> None:
    with pytest.raises(ValidationError):
        CreateConfigInput(name="x", description="")


def test_descricao_ausente_invalida() -> None:
    with pytest.raises(ValidationError):
        CreateConfigInput(name="x")  # type: ignore[call-arg]


def test_draft_input_descricao_em_branco_invalida() -> None:
    with pytest.raises(ValidationError):
        DraftInput(name="x", description="", payload=ConfigPayload(model_id="gpt-4o"))


def test_alterar_descricao_de_publicado_cria_rascunho(
    session: Session, payload: ConfigPayload
) -> None:
    repo = ConfigRepository(session)
    svc = ConfigService(repo)

    config = svc.create_config("agente-desc", description="Descrição inicial")
    svc.save_draft(config.id, payload, "autor")
    svc.publish(config.id, "autor")

    config_pub = repo.get_config(config.id)
    assert config_pub is not None
    assert config_pub.draft_version_id is None

    nova_desc = "Descrição atualizada"
    svc.update_draft(
        config.id, name="agente-desc", description=nova_desc, payload=payload, author="autor"
    )

    config_apos = repo.get_config(config.id)
    assert config_apos is not None
    assert config_apos.description == nova_desc
    assert config_apos.draft_version_id is not None
