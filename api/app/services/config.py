from uuid import UUID

from app.agents.capabilities import validate_capabilities
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import ConfigKind, ConfigPayload, ConfigPayloadStatus


class ConfigService:
    def __init__(self, repo: ConfigRepository, servers: McpServerRepository | None = None) -> None:
        self._repo = repo
        self._servers = servers

    def create_config(
        self, name: str, description: str, kind: ConfigKind = ConfigKind.agent
    ) -> AgentConfig:
        return self._repo.create_config(name=name, description=description, kind=kind)

    def save_draft(
        self, config_id: UUID, payload: ConfigPayload, author: str
    ) -> AgentConfigVersion:
        config = self._get_or_raise(config_id)
        self._validate(config, payload)
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
        config = self._get_or_raise(config_id)
        self._validate(config, payload)
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
        kind: ConfigKind | None = None,
    ) -> tuple[list[AgentConfig], int]:
        return self._repo.list_configs(
            page=page, page_size=page_size, q=q, status=status, kind=kind
        )

    def _get_or_raise(self, config_id: UUID) -> AgentConfig:
        config = self._repo.get_config(config_id)
        if config is None:
            raise ValueError(f"Config {config_id} não encontrada")
        return config

    def _validate(self, config: AgentConfig, payload: ConfigPayload) -> None:
        errors = validate_capabilities(payload.model_id, payload.capabilities)
        errors += self._mcp_errors(payload)
        errors += self._team_errors(config, payload)
        if errors:
            raise ValueError("; ".join(errors))

    def _team_errors(self, config: AgentConfig, payload: ConfigPayload) -> list[str]:
        """Membros existem, são agentes publicados e a versão fixada é deles (ADR-0011)."""
        if config.kind != ConfigKind.team:
            return ["só time tem seção 'team'"] if payload.team is not None else []
        if payload.team is None:
            return ["time precisa da seção 'team' com ao menos um membro"]
        errors: list[str] = []
        for member in payload.team.members:
            agent = self._repo.get_config(member.agent_id)
            if agent is None:
                errors.append(f"membro {member.agent_id} não existe")
                continue
            if agent.kind != ConfigKind.agent:
                errors.append(f"'{agent.name}' é um time; time dentro de time não é suportado")
                continue
            if agent.current_version_id is None:
                errors.append(f"'{agent.name}' não tem versão publicada")
            if member.version_id is not None:
                version = self._repo.get_version(member.version_id)
                if (
                    version is None
                    or version.config_id != agent.id
                    or version.status != ConfigPayloadStatus.published
                ):
                    errors.append(
                        f"versão fixada de '{agent.name}' não é uma versão publicada dele"
                    )
        return errors

    def _mcp_errors(self, payload: ConfigPayload) -> list[str]:
        if not payload.mcp_servers:
            return []
        if self._servers is None:
            raise RuntimeError("ConfigService sem McpServerRepository para validar mcp_servers")
        found = {
            s.id: s for s in self._servers.get_many([b.server_id for b in payload.mcp_servers])
        }
        errors: list[str] = []
        for binding in payload.mcp_servers:
            server = found.get(binding.server_id)
            if server is None:
                errors.append(f"servidor MCP {binding.server_id} não existe")
                continue
            if server.tools_snapshot is None:
                # nunca descoberto: a lista de tools não tem contra o que conferir
                continue
            known = {t["name"] for t in server.tools_snapshot}
            pedidas = set(binding.tools or []) | set(binding.require_confirmation)
            faltando = pedidas - known
            if faltando:
                errors.append(f"tools inexistentes em '{server.slug}': {sorted(faltando)}")
        return errors
