"""Casos de teste por agente e time (ADR-0015). Ficam fora do payload versionado."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.workflow import NEEDS_VALUE, WorkflowRule

# mensagens anteriores por caso; cada uma é um run do modelo antes do turno avaliado
MAX_CONTEXT = 5
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
    # turnos anteriores da conversa; só a resposta a `input` passa pelas checagens
    context: list[Annotated[str, Field(min_length=1, max_length=4000)]] = Field(
        default_factory=list, max_length=MAX_CONTEXT
    )
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
    context: list[str]
    checks: list[EvalCheck]
    position: int
    updated_by: str
    created_at: datetime
    updated_at: datetime


EvalRunStatus = Literal["queued", "running", "completed", "failed"]
EvalResultStatus = Literal["passed", "failed", "error", "not_evaluated"]
EvalTrigger = Literal["manual", "integration", "schedule"]
EvalTarget = Literal["draft", "current"]
# pending enquanto roda; passed só com a suíte completa e todos os casos aprovados
EvalVerdict = Literal["pending", "passed", "failed"]


class EvalRunCreate(BaseModel):
    # sem versão nem alvo: o rascunho, se houver; senão, a vigente
    version_id: UUID | None = None
    # apelido para quem não conhece ids de versão (CI de consumidor, agendamento)
    target: EvalTarget | None = None
    # obrigatório quando algum caso tem checagem de juiz, salvo no modo demo
    judge_model: str | None = None

    @model_validator(mode="after")
    def versao_ou_alvo(self) -> "EvalRunCreate":
        if self.version_id is not None and self.target is not None:
            raise ValueError("Informe version_id ou target, não os dois")
        return self


class EvalRunSummary(BaseModel):
    id: UUID
    agent_config_id: UUID
    version_id: UUID
    version_number: int
    version_status: str
    status: EvalRunStatus
    total: int
    passed: int
    failed: int
    not_evaluated: int
    error: str | None
    judge_model: str | None
    # casos e juiz, somados do usage_event da execução
    total_tokens: int
    cost: float | None
    started_by: str
    trigger: EvalTrigger
    target: EvalTarget | None
    verdict: EvalVerdict
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvalResultResponse(BaseModel):
    id: UUID
    case_id: UUID | None
    case_name: str
    position: int
    status: EvalResultStatus
    # uma entrada por checagem, com "type", "passed" (null quando não rodou) e o detalhe
    checks: list[dict[str, Any]]
    output: str | None
    tools_called: list[str]
    duration_ms: int | None
    error: str | None
    session_id: str | None


class EvalRunDetail(EvalRunSummary):
    results: list[EvalResultResponse]


class EvalSettingsInput(BaseModel):
    require_passing_evals: bool


class EvalSettings(BaseModel):
    require_passing_evals: bool
    draft_version_id: UUID | None
    # última execução no rascunho atual, se houver
    draft_run: EvalRunSummary | None
    # se o gate liberaria publicar agora; sem gate ligado, sempre true
    can_publish: bool
    reason: str | None


CaseChange = Literal["regression", "fix", "same", "new", "removed"]


class CaseComparison(BaseModel):
    case_id: UUID | None
    case_name: str
    base_status: EvalResultStatus | None
    target_status: EvalResultStatus | None
    change: CaseChange


class EvalComparison(BaseModel):
    base: EvalRunSummary
    target: EvalRunSummary
    cases: list[CaseComparison]
    regressions: int
    fixes: int


class EvalScheduleInput(BaseModel):
    # cron de 5 campos; o painel oferece frequências prontas e cron livre como avançado
    cron_expr: str = Field(min_length=9, max_length=64)
    timezone: str = Field(default="America/Sao_Paulo", max_length=64)
    target: EvalTarget = "current"
    judge_model: str | None = None
    enabled: bool = True


class EvalScheduleResponse(BaseModel):
    agent_config_id: UUID
    cron_expr: str
    timezone: str
    target: EvalTarget
    judge_model: str | None
    enabled: bool
    next_run_at: datetime | None
    last_attempt_at: datetime | None
    last_run_id: UUID | None
    # por que o último horário não virou execução
    last_error: str | None
    updated_by: str
    updated_at: datetime


SuiteStateName = Literal["running", "passing", "failing", "regressed"]


class EvalSuiteStatus(BaseModel):
    config_id: UUID
    # regressed: a execução agendada mais recente perdeu caso que passava na agendada anterior
    state: SuiteStateName
    last_run: EvalRunSummary
    previous_run_id: UUID | None
    regressions: int
