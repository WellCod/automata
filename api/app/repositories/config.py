from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.config import AgentConfig, AgentConfigVersion
from app.schemas.config import ConfigKind, ConfigPayload, ConfigPayloadStatus


class ConfigRepository:
    """Configs (agente, time, workflow) e suas versões imutáveis."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def count_configs(self) -> int:
        return int(self._session.scalar(select(func.count()).select_from(AgentConfig)) or 0)

    def get_config(self, config_id: UUID) -> AgentConfig | None:
        return self._session.get(AgentConfig, config_id)

    def names_by_ids(self, config_ids: list[UUID]) -> dict[UUID, str]:
        if not config_ids:
            return {}
        rows = self._session.execute(
            select(AgentConfig.id, AgentConfig.name).where(AgentConfig.id.in_(config_ids))
        ).all()
        return {row.id: row.name for row in rows}

    def teams_using(self, agent_id: UUID) -> list[AgentConfig]:
        """Times cuja versão vigente ou rascunho tem o agente como membro."""
        # `@>` do JSONB: a lista de membros contém um com esse agent_id
        member = [{"agent_id": str(agent_id)}]
        version_ids = select(AgentConfigVersion.id).where(
            AgentConfigVersion.payload["team"]["members"].contains(member)
        )
        stmt = (
            select(AgentConfig)
            .where(
                AgentConfig.kind == ConfigKind.team.value,
                (AgentConfig.current_version_id.in_(version_ids))
                | (AgentConfig.draft_version_id.in_(version_ids)),
            )
            .order_by(AgentConfig.name)
        )
        return list(self._session.scalars(stmt))

    def create_config(
        self, name: str, description: str, kind: ConfigKind = ConfigKind.agent
    ) -> AgentConfig:
        config = AgentConfig(name=name, description=description, kind=kind.value)
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
        """Grava uma versão nova com o próximo número; versão existente nunca muda."""
        # a linha do config serializa quem cria versão do mesmo config (OPS-11)
        self._session.execute(
            select(AgentConfig.id).where(AgentConfig.id == config_id).with_for_update()
        )
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
            payload=payload.model_dump(mode="json"),
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
        kind: ConfigKind | None = None,
    ) -> tuple[list[AgentConfig], int]:
        """Página de configs, mais recentes primeiro, com o total para a paginação.

        `q` que é um UUID busca pelo id; qualquer outro texto busca no nome.
        """
        base = select(AgentConfig)
        if kind is not None:
            base = base.where(AgentConfig.kind == kind.value)

        if q is not None:
            try:
                config_id = UUID(q)
                base = base.where(AgentConfig.id == config_id)
            except ValueError:
                base = base.where(AgentConfig.name.ilike(f"%{q}%"))

        if status == ConfigPayloadStatus.published:
            base = base.where(AgentConfig.current_version_id.is_not(None))
        elif status == ConfigPayloadStatus.draft:
            base = base.where(AgentConfig.draft_version_id.is_not(None))

        count_result = self._session.scalar(select(func.count()).select_from(base.subquery()))
        total = int(count_result) if count_result is not None else 0

        # versões carregadas junto: a lista mostra cada config sem uma consulta por linha
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
