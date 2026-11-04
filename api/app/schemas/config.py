import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.guardrails.pii import PII_TYPES, CustomPattern, PiiType
from app.schemas.workflow import WorkflowSettings


class ConfigPayloadStatus(enum.StrEnum):
    draft = "draft"
    published = "published"


class ConfigKind(enum.StrEnum):
    agent = "agent"
    team = "team"
    workflow = "workflow"


class InstructionSections(BaseModel):
    persona: str = ""
    situation: str = ""
    tone: str = ""
    objective: str = ""
    guardrails: str = ""


class CapabilityFlags(BaseModel):
    extended_thinking: bool = False
    structured_output: bool = False
    vision: bool = False


class McpServerBinding(BaseModel):
    """Servidor MCP que o agente usa e quais tools dele (ADR-0010)."""

    server_id: UUID
    # None libera todas as tools do servidor
    tools: list[str] | None = None
    # Tools que pausam o run até alguém confirmar no painel
    require_confirmation: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def confirmacao_dentro_das_liberadas(self) -> "McpServerBinding":
        if self.tools is not None:
            fora = set(self.require_confirmation) - set(self.tools)
            if fora:
                raise ValueError(f"tools com confirmação não liberadas: {sorted(fora)}")
        return self


class KnowledgeBinding(BaseModel):
    """Base de conhecimento que o agente consulta (ADR-0012). A base em si não é versionada."""

    base_id: UUID
    max_results: int = Field(default=5, ge=1, le=20)


class CustomPiiPattern(BaseModel):
    """Dado pessoal da empresa (matrícula, contrato, protocolo) pelo formato (ADR-0032).

    Sem regex livre: prefixo literal e a faixa de dígitos, montados em regex pelo código.
    """

    # vira "[<rótulo> removido]"
    label: str = Field(min_length=1, max_length=30, pattern=r"^[\w ]+$")
    # sem prefixo, qualquer número com essa quantidade de dígitos é mascarado
    prefix: str = Field(default="", max_length=10, pattern=r"^[A-Za-z0-9-]*$")
    min_digits: int = Field(ge=4, le=20)
    max_digits: int = Field(ge=4, le=20)

    @field_validator("label")
    @classmethod
    def rotulo_sem_espaco_nas_pontas(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("o rótulo precisa de texto")
        return v.strip()

    @model_validator(mode="after")
    def faixa_valida(self) -> "CustomPiiPattern":
        if self.min_digits > self.max_digits:
            raise ValueError("o mínimo de dígitos passa do máximo")
        return self

    def compiled(self) -> CustomPattern:
        return CustomPattern(self.label, self.prefix, self.min_digits, self.max_digits)


class PiiRule(BaseModel):
    # off: não olha; mask: troca o dado por um marcador e segue; block: mascara e bloqueia
    mode: Literal["off", "mask", "block"] = "off"
    types: list[PiiType] = Field(default_factory=lambda: list(PII_TYPES))
    # valem na entrada, na memória do usuário e no guardrail de saída
    custom: list[CustomPiiPattern] = Field(default_factory=list, max_length=10)

    @field_validator("custom")
    @classmethod
    def rotulos_unicos(cls, v: list[CustomPiiPattern]) -> list[CustomPiiPattern]:
        labels = [p.label.lower() for p in v]
        if len(labels) != len(set(labels)):
            raise ValueError("rótulo repetido nos padrões próprios")
        return v

    def custom_patterns(self) -> tuple[CustomPattern, ...]:
        return tuple(p.compiled() for p in self.custom)


class OutputRule(BaseModel):
    """Validação da resposta. No stream o texto já saiu quando ela roda (ADR-0013)."""

    pii: bool = False
    pii_types: list[PiiType] = Field(default_factory=lambda: list(PII_TYPES))
    blocked_terms: list[str] = Field(default_factory=list, max_length=50)
    # depois dos termos e dos dados pessoais; no stream, só marca o run (ADR-0034)
    classifier: "OutputClassifierRule | None" = None

    @field_validator("blocked_terms")
    @classmethod
    def termos_validos(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t.strip()]
        if any(len(t) < 3 or len(t) > 100 for t in cleaned):
            raise ValueError("cada termo precisa ter de 3 a 100 caracteres")
        return cleaned


DEFAULT_BLOCKED_MESSAGE = "Não posso ajudar com essa mensagem por aqui."


ClassifierCheck = Literal["injection", "toxicity", "off_topic"]


class ClassifierRule(BaseModel):
    """Classificador por modelo na entrada (ADR-0030): uma chamada por mensagem."""

    model_id: str = Field(min_length=1, max_length=64)
    checks: list[ClassifierCheck] = Field(min_length=1, max_length=3)
    # o que o agente atende, em texto; obrigatório com off_topic
    scope: str = Field(default="", max_length=500)
    # classificador fora do ar ou sem resposta em 10 s: deixa passar ou bloqueia
    on_failure: Literal["allow", "block"] = "allow"

    @model_validator(mode="after")
    def escopo_com_off_topic(self) -> "ClassifierRule":
        if len(self.checks) != len(set(self.checks)):
            raise ValueError("checagem repetida no classificador")
        if "off_topic" in self.checks and not self.scope.strip():
            raise ValueError("o classificador de assunto precisa do escopo do agente")
        return self


OutputClassifierCheck = Literal["toxicity", "off_topic", "prompt_leak"]


class OutputClassifierRule(BaseModel):
    """Classificador por modelo na resposta (ADR-0034): uma chamada por resposta."""

    model_id: str = Field(min_length=1, max_length=64)
    checks: list[OutputClassifierCheck] = Field(min_length=1, max_length=3)
    scope: str = Field(default="", max_length=500)
    on_failure: Literal["allow", "block"] = "allow"

    @model_validator(mode="after")
    def escopo_com_off_topic(self) -> "OutputClassifierRule":
        if len(self.checks) != len(set(self.checks)):
            raise ValueError("checagem repetida no classificador da saída")
        if "off_topic" in self.checks and not self.scope.strip():
            raise ValueError("o classificador de assunto precisa do escopo do agente")
        return self


# OutputRule vem antes e cita o classificador da saída pelo nome
OutputRule.model_rebuild()


class ToolResultScreening(BaseModel):
    """Resultado de tool examinado antes de voltar ao modelo (ADR-0030)."""

    # termos de injeção do ADR-0013, os de conteúdo de terceiros e os extras do agente
    terms: bool = True
    # também pelo classificador, só com a checagem injection: uma chamada por tool
    classifier: bool = False


class GuardrailSettings(BaseModel):
    """Regras de entrada do agente (ADR-0013). Tudo desligado por padrão."""

    pii: PiiRule = Field(default_factory=PiiRule)
    prompt_injection: bool = False
    # somam à lista padrão em português e inglês
    injection_extra_terms: list[str] = Field(default_factory=list, max_length=50)
    blocked_topics: list[str] = Field(default_factory=list, max_length=50)
    max_input_chars: int | None = Field(default=None, ge=50, le=100_000)
    # API de moderação da OpenAI: uma chamada por mensagem, com o texto saindo da instância
    moderation: bool = False
    classifier: ClassifierRule | None = None
    tool_results: ToolResultScreening | None = None
    output: OutputRule = Field(default_factory=OutputRule)
    blocked_message: str = Field(default=DEFAULT_BLOCKED_MESSAGE, min_length=1, max_length=500)

    @field_validator("injection_extra_terms", "blocked_topics")
    @classmethod
    def termos_validos(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip() for t in v if t.strip()]
        if any(len(t) < 3 or len(t) > 100 for t in cleaned):
            raise ValueError("cada termo precisa ter de 3 a 100 caracteres")
        return cleaned


TeamModeName = Literal["coordinate", "route", "broadcast", "tasks"]


class TeamMember(BaseModel):
    agent_id: UUID
    # None segue a versão vigente do agente; preenchido fixa a versão (ADR-0011)
    version_id: UUID | None = None


class ConversationSettings(BaseModel):
    """Conversa longa (ADR-0019): turnos antigos viram resumo acima de um limite de tokens."""

    compaction: bool = False
    # bem abaixo dos 150 mil do Agno: com a compactação ligada, a janela vai até o limite
    compact_at_tokens: int = Field(default=16_000, ge=4_000, le=128_000)
    # turnos recentes mantidos inteiros
    keep_recent_runs: int = Field(default=3, ge=1, le=20)
    # o que o resumo não pode perder, ex.: "mantenha números de pedido e CPF mascarado"
    summary_instructions: str | None = Field(default=None, max_length=500)
    # tool de busca no histórico compactado, para o detalhe que o resumo deixou de fora
    search_history: bool = True
    # modelo da matriz que escreve o resumo (ADR-0035); vazio usa o do agente
    summary_model: str | None = Field(default=None, min_length=1, max_length=64)


class MemorySettings(BaseModel):
    """Memória do usuário entre sessões (ADR-0025): só deste agente, mascarada e com prazo."""

    enabled: bool = False
    # o que vale lembrar, ex.: "preferências de entrega e tamanho que veste"
    instructions: str | None = Field(default=None, max_length=500)
    retention_days: int = Field(default=90, ge=1, le=365)


class ToolCompression(BaseModel):
    """Resultado de tool resumido por um modelo antes de seguir no contexto (ADR-0029)."""

    # comprime quando há esse número de resultados ainda inteiros no contexto
    after_results: int = Field(default=3, ge=1, le=10)
    # ou quando o contexto passa desse número de tokens
    token_limit: int | None = Field(default=None, ge=2000, le=200_000)
    # vazio = o modelo do próprio agente
    model_id: str | None = Field(default=None, max_length=64)


class RunControls(BaseModel):
    """Controle do run (ADR-0027). Padrão vazio: nenhum agente publicado muda sem versão nova."""

    # chamadas além do limite voltam ao modelo como erro, sem executar a tool
    tool_call_limit: int | None = Field(default=None, ge=1, le=100)
    # repete só a chamada ao provedor que falhou, com espera de 1, 2 e 4 s; o run, nunca
    provider_retries: int = Field(default=0, ge=0, le=3)
    # em ordem, quando o principal falha de vez (5xx, rede) ou responde 429
    fallback_models: list[str] = Field(default_factory=list, max_length=2)
    # vazio = resultado de tool inteiro no contexto, como antes
    compress_tool_results: ToolCompression | None = None
    # teto de custo das chamadas ao modelo do run, conferido antes de cada tool (ADR-0031)
    max_cost_usd: float | None = Field(default=None, ge=0.01, le=100)

    @model_validator(mode="after")
    def reservas_unicas(self) -> "RunControls":
        if len(self.fallback_models) != len(set(self.fallback_models)):
            raise ValueError("modelo reserva repetido")
        return self


class TeamSettings(BaseModel):
    """Seção de time do payload. Só existe em config de kind=team."""

    mode: TeamModeName = "coordinate"
    members: list[TeamMember] = Field(min_length=1, max_length=20)
    max_iterations: int = Field(default=10, ge=1, le=50)
    share_member_interactions: bool = False

    @model_validator(mode="after")
    def membros_unicos(self) -> "TeamSettings":
        ids = [m.agent_id for m in self.members]
        if len(ids) != len(set(ids)):
            raise ValueError("membro repetido no time")
        return self


class ConfigPayload(BaseModel):
    """Payload JSONB de uma versão de configuração.

    schema_version é guardado dentro do payload para permitir migrações
    de formato sem alterar a coluna — a lógica de upgrade fica no código,
    não no schema do banco.

    v1 → v2: `tools: list[str]`, que nunca chegou ao agente, dá lugar a
    `mcp_servers`. Versões v1 gravadas são convertidas na leitura.
    """

    schema_version: Literal[2] = 2
    # obrigatório em agente e time (validado no serviço); workflow não tem modelo próprio
    model_id: str | None = None
    instructions: InstructionSections = Field(default_factory=InstructionSections)
    mcp_servers: list[McpServerBinding] = Field(default_factory=list)
    knowledge: list[KnowledgeBinding] = Field(default_factory=list, max_length=10)
    guardrails: GuardrailSettings = Field(default_factory=GuardrailSettings)
    capabilities: CapabilityFlags = Field(default_factory=CapabilityFlags)
    conversation: ConversationSettings = Field(default_factory=ConversationSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    run: RunControls = Field(default_factory=RunControls)
    # JSON Schema da resposta (ADR-0027); com ele o agente devolve objeto, não texto
    output_schema: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Em time: modelo, instruções e MCP acima são do líder
    team: TeamSettings | None = None
    # Em workflow: árvore de etapas (ADR-0014); modelo e instruções não se aplicam
    workflow: WorkflowSettings | None = None

    @model_validator(mode="before")
    @classmethod
    def upgrade_v1(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("schema_version", 1) == 1:
            data = {k: v for k, v in data.items() if k != "tools"}
            data["schema_version"] = 2
        return data

    @model_validator(mode="after")
    def servidores_unicos(self) -> "ConfigPayload":
        ids = [b.server_id for b in self.mcp_servers]
        if len(ids) != len(set(ids)):
            raise ValueError("servidor MCP repetido no agente")
        bases = [b.base_id for b in self.knowledge]
        if len(bases) != len(set(bases)):
            raise ValueError("base de conhecimento repetida no agente")
        return self


class AgentConfigVersionSummary(BaseModel):
    id: UUID
    version_number: int
    label: str | None
    status: ConfigPayloadStatus
    author: str
    created_at: datetime


class AgentConfigResponse(BaseModel):
    id: UUID
    kind: ConfigKind
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    current_version: AgentConfigVersionSummary | None
    draft_version: AgentConfigVersionSummary | None


class AgentConfigPage(BaseModel):
    items: list[AgentConfigResponse]
    total: int
    page: int
    page_size: int


class AgentConfigDetail(AgentConfigResponse):
    payload: ConfigPayload | None


class DraftInput(BaseModel):
    name: str
    description: str = Field(min_length=1)
    payload: ConfigPayload


class AgentConfigVersionDetail(AgentConfigVersionSummary):
    payload: ConfigPayload


class RollbackInput(BaseModel):
    version_id: UUID


class CreateConfigInput(BaseModel):
    name: str
    description: str = Field(min_length=1)
    kind: ConfigKind = ConfigKind.agent
