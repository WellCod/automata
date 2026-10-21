"""Casos de teste por agente e time (ADR-0015). Ficam fora do payload versionado."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.workflow import NEEDS_VALUE, WorkflowRule

MAX_CASES = 50
MAX_CHECKS = 5

TextKind = Literal["contains", "not_contains", "starts_with", "empty", "not_empty"]

# nome de tool como o agente expõe: buscar_<slug> das bases, <slug>_<tool> do MCP
_ToolName = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.\-]+$")]


class TextCheck(BaseModel):
    """Regra sobre a resposta, a mesma dos workflows; "sempre" não entra, passaria sem checar."""

    type: Literal["text"] = "text"
    kind: TextKind
    value: str = Field(default="", max_length=200)

    def rule(self) -> WorkflowRule:
        return WorkflowRule(kind=self.kind, source="previous", value=self.value)

    @model_validator(mode="after")
    def valor_quando_precisa(self) -> "TextCheck":
        if self.kind in NEEDS_VALUE and not self.value.strip():
            raise ValueError(f"regra '{self.kind}' precisa de um texto")
        return self


class ToolsCheck(BaseModel):
    """Tools que o run precisa chamar (ReliabilityEval do Agno)."""

    type: Literal["tools"] = "tools"
    tools: list[_ToolName] = Field(min_length=1, max_length=10)
    # com False, qualquer tool fora da lista reprova o caso
    allow_additional: bool = True

    @field_validator("tools")
    @classmethod
    def sem_repeticao(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("tool repetida na lista")
        return v


class JudgeCheck(BaseModel):
    """Critério avaliado por um modelo juiz (AgentAsJudgeEval do Agno)."""

    type: Literal["judge"] = "judge"
    criteria: str = Field(min_length=10, max_length=1000)
    mode: Literal["binary", "numeric"] = "binary"
    # só vale no modo numérico: nota de 1 a 10 que aprova
    threshold: int = Field(default=7, ge=1, le=10)


EvalCheck = Annotated[TextCheck | ToolsCheck | JudgeCheck, Field(discriminator="type")]


class EvalCaseInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    input: str = Field(min_length=1, max_length=4000)
    checks: list[EvalCheck] = Field(min_length=1, max_length=MAX_CHECKS)

    @field_validator("name")
    @classmethod
    def nome_limpo(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("nome obrigatório")
        return v

    @model_validator(mode="after")
    def um_por_tipo_no_runner(self) -> "EvalCaseInput":
        # o Case do Agno tem um campo de critério e um de tools; texto vira um scorer só
        for kind in ("tools", "judge"):
            if sum(1 for c in self.checks if c.type == kind) > 1:
                raise ValueError(f"no máximo uma checagem do tipo {kind} por caso")
        return self


class EvalCaseResponse(BaseModel):
    id: UUID
    agent_config_id: UUID
    name: str
    input: str
    checks: list[EvalCheck]
    position: int
    updated_by: str
    created_at: datetime
    updated_at: datetime
