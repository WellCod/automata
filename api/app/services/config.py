from uuid import UUID

from app.agents.capabilities import validate_capabilities
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.schemas.config import ConfigPayload, ConfigPayloadStatus


class ConfigService:
    def __init__(self, repo: ConfigRepository) -> None:
        self._repo = repo

    def create_config(self, name: str, description: str) -> AgentConfig:
        return self._repo.create_config(name=name, description=description)

    def save_draft(
        self, config_id: UUID, payload: ConfigPayload, author: str
    ) -> AgentConfigVersion:
        errors = validate_capabilities(payload.model_id, payload.capabilities)
        if errors:
            raise ValueError("; ".join(errors))

        config = self._get_or_raise(config_id)
        version = self._repo.create_version(
            config_id=config_id,
            payload=payload,
            author=author,
            status=ConfigPayloadStatus.draft,
        )
        self._repo.set_draft_version(config, version.id)
        return version

    def publish(self, config_id: UUID, author: str) -> AgentConfigVersion:
        """Cria versão publicada a partir do rascunho e move o ponteiro.

        Nunca faz UPDATE em versão existente — cria uma linha nova com
        status=published e move current_version_id para ela.
        """
        config = self._get_or_raise(config_id)

        if config.draft_version_id is None:
            raise ValueError("Nenhum rascunho para publicar")

        draft = self._repo.get_version(config.draft_version_id)
        if draft is None:
            raise ValueError("Rascunho não encontrado")

        payload = ConfigPayload.model_validate(draft.payload)
        published = self._repo.create_version(
            config_id=config_id,
            payload=payload,
            author=author,
            status=ConfigPayloadStatus.published,
        )

        self._repo.set_current_version(config, published.id)
        self._repo.set_draft_version(config, None)
        return published

    def rollback(self, config_id: UUID, version_id: UUID) -> AgentConfig:
        """Move current_version_id para uma versão publicada anterior.

        Operação de ponteiro apenas — nenhum dado de versão é alterado.
        """
        config = self._get_or_raise(config_id)
        version = self._repo.get_version(version_id)

        if version is None:
            raise ValueError("Versão não encontrada")
        if version.config_id != config_id:
            raise ValueError("Versão não pertence a este agente")
        if version.status != ConfigPayloadStatus.published:
            raise ValueError("Rollback só é permitido para versão publicada")

        self._repo.set_current_version(config, version_id)
        return config

    def get_detail(self, config_id: UUID) -> tuple[AgentConfig, ConfigPayload | None]:
        config = self._get_or_raise(config_id)
        version_id = config.draft_version_id or config.current_version_id
        if version_id is None:
            return config, None
        version = self._repo.get_version(version_id)
        if version is None:
            return config, None
        return config, ConfigPayload.model_validate(version.payload)

    def update_draft(
        self,
        config_id: UUID,
        name: str,
        description: str,
        payload: ConfigPayload,
        author: str,
    ) -> AgentConfigVersion:
        errors = validate_capabilities(payload.model_id, payload.capabilities)
        if errors:
            raise ValueError("; ".join(errors))

        config = self._get_or_raise(config_id)
        self._repo.update_config(config, name=name, description=description)
        version = self._repo.create_version(
            config_id=config_id,
            payload=payload,
            author=author,
            status=ConfigPayloadStatus.draft,
        )
        self._repo.set_draft_version(config, version.id)
        return version

    def list_versions(self, config_id: UUID) -> list[AgentConfigVersion]:
        self._get_or_raise(config_id)
        return self._repo.list_versions(config_id)

    def list_configs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        status: ConfigPayloadStatus | None = None,
    ) -> tuple[list[AgentConfig], int]:
        return self._repo.list_configs(page=page, page_size=page_size, q=q, status=status)

    def _get_or_raise(self, config_id: UUID) -> AgentConfig:
        config = self._repo.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} não encontrada")
        return config
