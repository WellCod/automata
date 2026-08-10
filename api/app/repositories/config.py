from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigPayload, ConfigPayloadStatus


class ConfigRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_config(self, config_id: UUID) -> AgentConfig | None:
        return self._session.get(AgentConfig, config_id)

    def create_config(self, name: str, description: str) -> AgentConfig:
        config = AgentConfig(name=name, description=description)
        self._session.add(config)
        self._session.flush()
        return config

    def get_version(self, version_id: UUID) -> AgentConfigVersion | None:
        return self._session.get(AgentConfigVersion, version_id)

    def create_version(
        self,
        config_id: UUID,
        payload: ConfigPayload,
        author: str,
        status: ConfigPayloadStatus = ConfigPayloadStatus.draft,
    ) -> AgentConfigVersion:
        stmt = (
            select(AgentConfigVersion)
            .where(AgentConfigVersion.config_id == config_id)
            .order_by(AgentConfigVersion.version_number.desc())
            .limit(1)
        )
        last = self._session.scalar(stmt)
        next_number = (last.version_number + 1) if last else 1

        version = AgentConfigVersion(
            config_id=config_id,
            version_number=next_number,
            status=status,
            payload=payload.model_dump(),
            author=author,
        )
        self._session.add(version)
        self._session.flush()
        return version

    def set_current_version(self, config: AgentConfig, version_id: UUID | None) -> None:
        config.current_version_id = version_id
        self._session.flush()

    def set_draft_version(self, config: AgentConfig, version_id: UUID | None) -> None:
        config.draft_version_id = version_id
        self._session.flush()

    def update_config(self, config: AgentConfig, *, name: str, description: str) -> None:
        config.name = name
        config.description = description
        self._session.flush()

    def list_versions(self, config_id: UUID) -> list[AgentConfigVersion]:
        stmt = (
            select(AgentConfigVersion)
            .where(AgentConfigVersion.config_id == config_id)
            .order_by(AgentConfigVersion.version_number.desc())
        )
        return list(self._session.scalars(stmt))

    def list_configs(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        q: str | None = None,
        status: ConfigPayloadStatus | None = None,
    ) -> tuple[list[AgentConfig], int]:
        base = select(AgentConfig)

        if q is not None:
            try:
                uid = UUID(q)
                base = base.where(AgentConfig.id == uid)
            except ValueError:
                base = base.where(AgentConfig.name.ilike(f"%{q}%"))

        if status == ConfigPayloadStatus.published:
            base = base.where(AgentConfig.current_version_id.is_not(None))
        elif status == ConfigPayloadStatus.draft:
            base = base.where(AgentConfig.draft_version_id.is_not(None))

        count_result = self._session.scalar(select(func.count()).select_from(base.subquery()))
        total = int(count_result) if count_result is not None else 0

        rows = self._session.scalars(
            base.options(
                selectinload(AgentConfig.current_version),
                selectinload(AgentConfig.draft_version),
            )
            .order_by(AgentConfig.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(rows), total
