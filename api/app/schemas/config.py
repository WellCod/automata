import enum
from typing import Any, Literal

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
