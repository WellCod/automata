import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ConfigPayloadStatus(enum.StrEnum):
    draft = "draft"
    published = "published"


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


class ConfigPayload(BaseModel):
    """Payload JSONB de uma versão de configuração.

    schema_version é guardado dentro do payload para permitir migrações
    de formato sem alterar a coluna — a lógica de upgrade fica no código,
    não no schema do banco.
    """

    schema_version: Literal[1] = 1
    model_id: str
    instructions: InstructionSections = Field(default_factory=InstructionSections)
    tools: list[str] = Field(default_factory=list)
    capabilities: CapabilityFlags = Field(default_factory=CapabilityFlags)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentConfigVersionSummary(BaseModel):
    id: UUID
    version_number: int
    label: str | None
    status: ConfigPayloadStatus
    author: str
    created_at: datetime


class AgentConfigResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
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
    description: str | None = None
    payload: ConfigPayload


class AgentConfigVersionDetail(AgentConfigVersionSummary):
    payload: ConfigPayload


class RollbackInput(BaseModel):
    version_id: UUID


class CreateConfigInput(BaseModel):
    name: str
    description: str | None = None
