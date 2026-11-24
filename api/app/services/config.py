from uuid import UUID

from app.agents.capabilities import get_capabilities, validate_capabilities
from app.agents.output_schema import schema_problems
from app.guardrails.input import moderation_available
from app.knowledge.embedders import demo_replay
from app.models.config import AgentConfig, AgentConfigVersion
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import (
    ConfigKind,
    ConfigPayload,
    ConfigPayloadStatus,
    GuardrailSettings,
    RunControls,
)
from app.schemas.workflow import step_nodes


def guardrail_errors(guardrails: GuardrailSettings) -> list[str]:
    """Regras de escrita dos guardrails, do agente e do piso da instância (ADR-0034)."""
    # sem a chave, a moderação falharia a cada mensagem em produção
    errors: list[str] = []
    if guardrails.moderation and not (moderation_available() or demo_replay()):
        errors.append("moderação exige OPENAI_API_KEY na API")
    classifier = guardrails.classifier
    screening = guardrails.tool_results
    if screening is not None and screening.classifier and classifier is None:
        errors.append("o exame de tool pelo classificador exige o classificador configurado")
    if screening is not None and not (screening.terms or screening.classifier):
        errors.append("exame de tool sem termos nem classificador não examina nada")
    if classifier is not None:
        try:
            get_capabilities(classifier.model_id)
        except ValueError as exc:
            errors.append(f"modelo do classificador: {exc}")
    if guardrails.output.classifier is not None:
        try:
            get_capabilities(guardrails.output.classifier.model_id)
        except ValueError as exc:
            errors.append(f"modelo do classificador da saída: {exc}")
    return errors


class PlanLimitError(ValueError):
    """Passou do limite do plano (`PLAN_MAX_*`): o router responde 409."""


class ConfigService:
    """Ciclo de vida do config: rascunho, publicação, canário e rollback, com validação na escrita.

    Os repositórios de servidores MCP e de bases só são exigidos quando o payload os referencia.
    """

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
        """Cria o config vazio, respeitando o limite de configs do plano."""
        from app.settings import get_settings

        limit = get_settings().plan_max_configs
        if limit and self._repo.count_configs() >= limit:
            # limite do plano contratado (COM-06)
            raise PlanLimitError(f"o plano permite {limit} agentes, times e workflows")
        return self._repo.create_config(name=name, description=description, kind=kind)

    def save_draft(
        self, config_id: UUID, payload: ConfigPayload, author: str
    ) -> AgentConfigVersion:
        """Grava o payload como versão de rascunho nova e aponta o rascunho para ela."""
        config = self._get_or_raise(config_id)
        first_version = config.current_version_id is None and config.draft_version_id is None
        if first_version and config.kind in (ConfigKind.agent, ConfigKind.team):
            # agente novo não nasce sem defesa (ADR-0045, LLM-01)
            payload = payload.with_safe_defaults()
        self._validate(config, payload)
        version = self._repo.create_version(
            config_id=config_id,
            payload=payload,
            author=author,
            status=ConfigPayloadStatus.draft,
        )
        self._repo.set_draft_version(config, version.id)
        return version

    def publish_canary(self, config_id: UUID, author: str) -> AgentConfigVersion:
        """Publica o rascunho como versão nova sem mover a vigente (ADR-0040)."""
        config = self._get_or_raise(config_id)
        if config.draft_version_id is None:
            raise ValueError("Nenhum rascunho para publicar")
        draft = self._repo.get_version(config.draft_version_id)
        if draft is None:
            raise ValueError("Rascunho não encontrado")
        version = self._repo.create_version(
            config_id=config_id,
            payload=ConfigPayload.model_validate(draft.payload),
            author=author,
            status=ConfigPayloadStatus.published,
        )
        self._repo.set_draft_version(config, None)
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
        if config.kind != ConfigKind.workflow and self._needs_confirmation(payload):
            # etapa de workflow sem versão fixa passaria a rodar esta versão (LLM-11)
            workflows = self._workflows_following(config_id)
            if workflows:
                raise ValueError(
                    "este agente tem tool com confirmação humana, que não roda em workflow, e é"
                    f" etapa sem versão fixa de: {', '.join(workflows)}. Fixe a versão da etapa"
                    " ou tire a confirmação"
                )
        published = self._repo.create_version(
            config_id=config_id,
            payload=payload,
            author=author,
            status=ConfigPayloadStatus.published,
        )

        self._repo.set_current_version(config, published.id)
        self._repo.set_draft_version(config, None)
        stop_canary(config)
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
        stop_canary(config)
        return config

    def get_detail(self, config_id: UUID) -> tuple[AgentConfig, ConfigPayload | None]:
        """Config com o payload que o editor mostra: o rascunho, ou a vigente sem rascunho."""
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
        """Atualiza nome e descrição e grava o payload como rascunho novo."""
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
        """Junta todos os problemas do payload numa mensagem só, para o editor ver de uma vez."""
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
        errors += self._fallback_errors(payload)
        errors += self._compression_errors(payload)
        errors += self._schema_errors(config, payload)
        if config.kind == ConfigKind.workflow and payload.run != RunControls():
            # quem chama modelo e tool são os agentes e times das etapas, cada um com o seu
            errors.append("workflow não tem controle de run próprio")
        if payload.memory.enabled and config.kind == ConfigKind.workflow:
            # a memória é de quem conversa: agente ou líder do time (ADR-0035)
            errors.append("workflow não guarda memória do usuário; ligue nos agentes das etapas")
        if errors:
            raise ValueError("; ".join(errors))

    @staticmethod
    def _schema_errors(config: AgentConfig, payload: ConfigPayload) -> list[str]:
        """Schema de saída válido e com custo de validação limitado, só em agente e time."""
        if payload.output_schema is None:
            return []
        if config.kind == ConfigKind.workflow:
            return ["workflow não tem saída estruturada própria"]
        errors = schema_problems(payload.output_schema)
        if not payload.capabilities.structured_output:
            # a capability é o que valida o modelo e as reservas contra a matriz
            errors.append("schema de saída exige a capability structured_output ligada")
        return errors

    @staticmethod
    def _fallback_errors(payload: ConfigPayload) -> list[str]:
        """Reserva da matriz, diferente do principal e com o que o agente liga (ADR-0027)."""
        errors: list[str] = []
        for model_id in payload.run.fallback_models:
            if model_id == payload.model_id:
                errors.append(f"modelo reserva '{model_id}' é o próprio modelo principal")
                continue
            try:
                missing = validate_capabilities(model_id, payload.capabilities)
            except ValueError as exc:
                errors.append(f"modelo reserva: {exc}")
                continue
            errors += [f"modelo reserva: {problem}" for problem in missing]
        return errors

    @staticmethod
    def _compression_errors(payload: ConfigPayload) -> list[str]:
        """Modelos da compressão (ADR-0029) e do resumo (ADR-0035) só da matriz; recebem texto."""
        errors: list[str] = []
        compression = payload.run.compress_tool_results
        if compression is not None and compression.model_id is not None:
            try:
                get_capabilities(compression.model_id)
            except ValueError as exc:
                errors.append(f"modelo da compressão: {exc}")
        summary_model = payload.conversation.summary_model
        if summary_model is not None:
            try:
                get_capabilities(summary_model)
            except ValueError as exc:
                errors.append(f"modelo do resumo da conversa: {exc}")
        return errors

    def _model_errors(self, config: AgentConfig, payload: ConfigPayload) -> list[str]:
        """Agente e time precisam de modelo; workflow não pode ter."""
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
                kind_label = "agente" if expected == ConfigKind.agent else "time"
                errors.append(f"etapa '{step.name}': {kind_label} {target_id} não existe")
                continue
            if target.current_version_id is None:
                errors.append(f"etapa '{step.name}': '{target.name}' não tem versão publicada")
                continue
            # sem versão fixada, a etapa segue a vigente do agente ou time
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

    def _workflows_following(self, config_id: UUID) -> list[str]:
        """Workflows publicados com etapa que segue a versão vigente deste config."""
        names: list[str] = []
        configs, _ = self._repo.list_configs(page_size=1000, kind=ConfigKind.workflow)
        for workflow in configs:
            if workflow.current_version_id is None:
                continue
            version = self._repo.get_version(workflow.current_version_id)
            if version is None:
                continue
            workflow_settings = ConfigPayload.model_validate(version.payload).workflow
            if workflow_settings is None:
                continue
            for step in step_nodes(workflow_settings.steps):
                if (step.agent_id or step.team_id) == config_id and step.version_id is None:
                    names.append(workflow.name)
                    break
        return names

    def _needs_confirmation(self, payload: ConfigPayload) -> bool:
        """Se o agente, ou algum membro do time na versão que roda, tem tool com confirmação."""
        if any(binding.require_confirmation for binding in payload.mcp_servers):
            return True
        if payload.team is None:
            return False
        for member in payload.team.members:
            agent = self._repo.get_config(member.agent_id)
            member_version_id = member.version_id or (agent.current_version_id if agent else None)
            version = self._repo.get_version(member_version_id) if member_version_id else None
            if version is not None and any(
                binding.require_confirmation
                for binding in ConfigPayload.model_validate(version.payload).mcp_servers
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
        return guardrail_errors(payload.guardrails)

    def _knowledge_errors(self, payload: ConfigPayload) -> list[str]:
        """Bases citadas no payload que não existem."""
        if not payload.knowledge:
            return []
        if self._bases is None:
            raise RuntimeError("ConfigService sem KnowledgeBaseRepository para validar knowledge")
        base_ids = [binding.base_id for binding in payload.knowledge]
        found = {base.id for base in self._bases.get_many(base_ids)}
        return [
            f"base de conhecimento {base_id} não existe"
            for base_id in base_ids
            if base_id not in found
        ]

    def _mcp_errors(self, payload: ConfigPayload) -> list[str]:
        """Servidores MCP inexistentes e tools pedidas que o servidor não tem."""
        if not payload.mcp_servers:
            return []
        if self._servers is None:
            raise RuntimeError("ConfigService sem McpServerRepository para validar mcp_servers")
        server_ids = [binding.server_id for binding in payload.mcp_servers]
        found = {server.id: server for server in self._servers.get_many(server_ids)}
        errors: list[str] = []
        for binding in payload.mcp_servers:
            server = found.get(binding.server_id)
            if server is None:
                errors.append(f"servidor MCP {binding.server_id} não existe")
                continue
            if server.tools_snapshot is None:
                # nunca descoberto: a lista de tools não tem contra o que conferir
                continue
            known = {tool["name"] for tool in server.tools_snapshot}
            requested = set(binding.tools or []) | set(binding.require_confirmation)
            unknown = requested - known
            if unknown:
                errors.append(f"tools inexistentes em '{server.slug}': {sorted(unknown)}")
        return errors


def stop_canary(config: AgentConfig) -> None:
    """Publicar ou voltar desliga o canário: não sobra versão velha recebendo tráfego."""
    config.canary_version_id = None
    config.canary_percent = None
    config.canary_started_at = None
