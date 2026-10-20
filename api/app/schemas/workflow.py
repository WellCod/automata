"""Seção `workflow` do payload (ADR-0014): árvore de etapas sobre agentes e times publicados."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

MAX_STEPS = 30
MAX_DEPTH = 3

RuleKind = Literal["always", "contains", "not_contains", "starts_with", "empty", "not_empty"]
NEEDS_VALUE = {"contains", "not_contains", "starts_with"}


class WorkflowRule(BaseModel):
    """Condição avaliada em código nosso, sem CEL; texto comparado sem maiúsculas."""

    kind: RuleKind = "always"
    # "input": mensagem original do usuário; "previous": saída da etapa anterior
    source: Literal["input", "previous"] = "previous"
    value: str = Field(default="", max_length=200)

    @model_validator(mode="after")
    def valor_quando_precisa(self) -> "WorkflowRule":
        if self.kind in NEEDS_VALUE and not self.value.strip():
            raise ValueError(f"regra '{self.kind}' precisa de um texto")
        return self


_Name = Annotated[str, Field(min_length=1, max_length=60)]


class StepNode(BaseModel):
    type: Literal["step"] = "step"
    name: _Name
    agent_id: UUID | None = None
    team_id: UUID | None = None
    # None segue a versão vigente; preenchido fixa a versão
    version_id: UUID | None = None
    # "stop" para o workflow quando a etapa falha; "continue" passa o erro adiante
    on_error: Literal["stop", "continue"] = "stop"
    max_retries: int = Field(default=0, ge=0, le=3)

    @model_validator(mode="after")
    def um_executor(self) -> "StepNode":
        if (self.agent_id is None) == (self.team_id is None):
            raise ValueError(f"etapa '{self.name}' precisa de um agente ou de um time")
        return self


class ParallelNode(BaseModel):
    type: Literal["parallel"] = "parallel"
    name: _Name
    branches: list[StepNode] = Field(min_length=2, max_length=5)


class ConditionNode(BaseModel):
    type: Literal["condition"] = "condition"
    name: _Name
    rule: WorkflowRule
    steps: list["WorkflowNode"] = Field(min_length=1)
    else_steps: list["WorkflowNode"] = Field(default_factory=list)


class LoopNode(BaseModel):
    type: Literal["loop"] = "loop"
    name: _Name
    steps: list["WorkflowNode"] = Field(min_length=1)
    max_iterations: int = Field(default=3, ge=1, le=10)
    # avaliada na saída da última etapa de cada volta; None roda até max_iterations
    until: WorkflowRule | None = None


WorkflowNode = Annotated[
    StepNode | ParallelNode | ConditionNode | LoopNode, Field(discriminator="type")
]


def _children(node: "WorkflowNode") -> list["WorkflowNode"]:
    if isinstance(node, ParallelNode):
        return list(node.branches)
    if isinstance(node, ConditionNode):
        return [*node.steps, *node.else_steps]
    if isinstance(node, LoopNode):
        return list(node.steps)
    return []


def walk(nodes: list["WorkflowNode"], depth: int = 1) -> list[tuple["WorkflowNode", int]]:
    out: list[tuple[WorkflowNode, int]] = []
    for node in nodes:
        out.append((node, depth))
        out += walk(_children(node), depth + 1)
    return out


def step_nodes(nodes: list["WorkflowNode"]) -> list[StepNode]:
    return [n for n, _ in walk(nodes) if isinstance(n, StepNode)]


class WorkflowSettings(BaseModel):
    """Seção de workflow do payload. Só existe em config de kind=workflow."""

    steps: list[WorkflowNode] = Field(min_length=1)

    @model_validator(mode="after")
    def estrutura_valida(self) -> "WorkflowSettings":
        nodes = walk(self.steps)
        names = [n.name for n, _ in nodes]
        repetidos = sorted({n for n in names if names.count(n) > 1})
        if repetidos:
            # o Agno indexa saídas e métricas pelo nome da etapa
            raise ValueError(f"nomes de etapa repetidos: {repetidos}")
        if max(d for _, d in nodes) > MAX_DEPTH:
            raise ValueError(f"aninhamento de no máximo {MAX_DEPTH} níveis")
        if len(step_nodes(self.steps)) > MAX_STEPS:
            raise ValueError(f"no máximo {MAX_STEPS} etapas")
        if isinstance(self.steps[-1], ParallelNode):
            # a saída final seria só a do último ramo
            raise ValueError("o workflow não pode terminar num paralelo: adicione uma etapa depois")
        return self


ConditionNode.model_rebuild()
LoopNode.model_rebuild()
WorkflowSettings.model_rebuild()
