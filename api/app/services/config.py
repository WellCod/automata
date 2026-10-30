from uuid import UUID

from app.agents.capabilities import validate_capabilities
from app.guardrails.input import moderation_available
from app.knowledge.embedders import demo_replay
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import ConfigKind, ConfigPayload, ConfigPayloadStatus, RunControls
from app.schemas.workflow import step_nodes


class ConfigService:
    def __init__(
        self,
        repo: ConfigRepository,
        servers: McpServerRepository | None = None,
        bases: KnowledgeBaseRepository | None = None,
    ) -> None:
        self._repo = repo
        self._servers = servers
        self._bases = bases

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
        errors = self._model_errors(config, payload)
        if payload.model_id is not None:
            errors += validate_capabilities(payload.model_id, payload.capabilities)
        errors += self._mcp_errors(payload)
        errors += self._knowledge_errors(payload)
        errors += self._guardrail_errors(payload)
        errors += self._team_errors(config, payload)
        errors += self._workflow_errors(config, payload)
        if payload.conversation.compaction and config.kind != ConfigKind.agent:
            # o Team do Agno 3.1.8 não aceita compaction (ADR-0019)
            errors.append("só agente compacta a conversa")
        if config.kind == ConfigKind.workflow and payload.run != RunControls():
            # quem chama modelo e tool são os agentes e times das etapas, cada um com o seu
            errors.append("workflow não tem controle de run próprio")
        if payload.memory.enabled and config.kind != ConfigKind.agent:
            # memória do líder e dos membros se misturariam (ADR-0025)
            errors.append("só agente guarda memória do usuário")
        if errors:
            raise ValueError("; ".join(errors))

    def _model_errors(self, config: AgentConfig, payload: ConfigPayload) -> list[str]:
        if config.kind == ConfigKind.workflow:
            # workflow não chama modelo: quem chama são os agentes e times das etapas
            return ["workflow não tem modelo próprio"] if payload.model_id is not None else []
        return ["modelo obrigatório"] if payload.model_id is None else []

    def _workflow_errors(self, config: AgentConfig, payload: ConfigPayload) -> list[str]:
        """Etapas apontam para agentes e times publicados, sem pausa humana (ADR-0014)."""
        if config.kind != ConfigKind.workflow:
            return ["só workflow tem seção 'workflow'"] if payload.workflow is not None else []
        if payload.workflow is None:
            return ["workflow precisa da seção 'workflow' com ao menos uma etapa"]
        errors: list[str] = []
        for step in step_nodes(payload.workflow.steps):
            target_id = step.agent_id or step.team_id
            assert target_id is not None
            expected = ConfigKind.agent if step.agent_id else ConfigKind.team
            target = self._repo.get_config(target_id)
            if target is None or target.kind != expected:
                rotulo = "agente" if expected == ConfigKind.agent else "time"
                errors.append(f"etapa '{step.name}': {rotulo} {target_id} não existe")
                continue
            if target.current_version_id is None:
                errors.append(f"etapa '{step.name}': '{target.name}' não tem versão publicada")
                continue
            version_id = step.version_id or target.current_version_id
            version = self._repo.get_version(version_id)
            if (
                version is None
                or version.config_id != target.id
                or version.status != ConfigPayloadStatus.published
            ):
                errors.append(
                    f"etapa '{step.name}': versão fixada não é uma versão publicada de "
                    f"'{target.name}'"
                )
                continue
            if self._needs_confirmation(ConfigPayload.model_validate(version.payload)):
                errors.append(
                    f"etapa '{step.name}': '{target.name}' tem tool com confirmação humana, "
                    "que não é suportada em workflow"
                )
        return errors

    def _needs_confirmation(self, payload: ConfigPayload) -> bool:
        if any(b.require_confirmation for b in payload.mcp_servers):
            return True
        if payload.team is None:
            return False
        for member in payload.team.members:
            agent = self._repo.get_config(member.agent_id)
            vid = member.version_id or (agent.current_version_id if agent else None)
            version = self._repo.get_version(vid) if vid else None
            if version is not None and any(
                b.require_confirmation
                for b in ConfigPayload.model_validate(version.payload).mcp_servers
            ):
                return True
        return False

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

    def _guardrail_errors(self, payload: ConfigPayload) -> list[str]:
        # sem a chave, a moderação falharia a cada mensagem em produção
        if payload.guardrails.moderation and not (moderation_available() or demo_replay()):
            return ["moderação exige OPENAI_API_KEY na API"]
        return []

    def _knowledge_errors(self, payload: ConfigPayload) -> list[str]:
        if not payload.knowledge:
            return []
        if self._bases is None:
            raise RuntimeError("ConfigService sem KnowledgeBaseRepository para validar knowledge")
        ids = [b.base_id for b in payload.knowledge]
        found = {b.id for b in self._bases.get_many(ids)}
        return [f"base de conhecimento {i} não existe" for i in ids if i not in found]

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
