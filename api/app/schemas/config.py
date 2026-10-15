import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ConfigPayloadStatus(enum.StrEnum):
    draft = "draft"
    published = "published"


class ConfigKind(enum.StrEnum):
    agent = "agent"
    team = "team"


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


TeamModeName = Literal["coordinate", "route", "broadcast", "tasks"]


class TeamMember(BaseModel):
    agent_id: UUID
    # None segue a versão vigente do agente; preenchido fixa a versão (ADR-0011)
    version_id: UUID | None = None


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
    model_id: str
    instructions: InstructionSections = Field(default_factory=InstructionSections)
    mcp_servers: list[McpServerBinding] = Field(default_factory=list)
    capabilities: CapabilityFlags = Field(default_factory=CapabilityFlags)
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Em time: modelo, instruções e MCP acima são do líder
    team: TeamSettings | None = None

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
