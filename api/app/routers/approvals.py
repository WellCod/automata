"""Runs pausados aguardando decisão humana: tool de agente ou etapa de workflow.

A decisão em si é feita na rota do AgentOS. No agente,
`POST /agents/{id}/runs/{run_id}/continue`, reenviando cada item de
`tool_execution` com `confirmed` true ou false. No workflow (ADR-0023),
`POST /workflows/{id}/runs/{run_id}/continue` com os `step_requirements` lidos do
run e o ativo marcado. Aqui só se lista o pendente.
"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.authz import Scope, require_scopes, sees_everyone
from app.db import SessionDep
from app.models.config import AgentConfig
from app.repositories.run import RunRepository
from app.repositories.user import emails_by_id

router = APIRouter(
    prefix="/api/v1/approvals",
    tags=["approvals"],
    dependencies=[Depends(require_scopes(Scope.METRICS_READ))],
)


class PendingTool(BaseModel):
    tool_call_id: str | None
    tool_name: str | None
    tool_args: dict[str, Any] | None
    # ToolExecution serializado: o painel devolve com `confirmed` no continue
    tool_execution: dict[str, Any]


class PendingStep(BaseModel):
    step_id: str | None
    step_name: str | None
    # before: confirma antes de rodar; after: aprova a saída antes da próxima etapa;
    # loop: aprova a volta (encerra o laço) ou pede outra com comentário (ADR-0028)
    when: Literal["before", "after", "loop"]
    message: str | None
    output: str | None
    timeout_at: datetime | None
    retry_count: int = 0


class ApprovalItem(BaseModel):
    run_id: str
    agent_id: UUID
    agent_name: str
    kind: str
    session_id: str | None
    user_id: str
    # e-mail de quem pediu, quando é usuário do painel; senão o próprio id (Fase 44)
    requested_by: str = ""
    created_at: datetime
    tools: list[PendingTool]
    steps: list[PendingStep]


@router.get("", response_model=list[ApprovalItem])
def list_pending(
    request: Request,
    session: SessionDep,
    agent_id: UUID | None = Query(default=None),  # noqa: B008
) -> list[ApprovalItem]:
    """Runs pausados à espera de decisão humana, com as tools e etapas pendentes."""
    # a pendência traz argumentos de tool e saída de etapa, que são dados da conversa:
    # cada um vê as suas, o owner vê todas (o continue do Agno também exige o dono)
    user_id = None if sees_everyone(request) else str(getattr(request.state, "user_id", ""))
    runs = RunRepository(session).list_paused([agent_id] if agent_id else None, user_id=user_id)
    config_ids = list({run.agent_config_id for run in runs})
    configs = {
        config.id: config
        for config in session.scalars(select(AgentConfig).where(AgentConfig.id.in_(config_ids)))
    }
    emails = emails_by_id(session, {run.user_id for run in runs})
    return [
        ApprovalItem(
            run_id=paused_run.run_id or "",
            agent_id=paused_run.agent_config_id,
            agent_name=(
                configs[paused_run.agent_config_id].name
                if paused_run.agent_config_id in configs
                else ""
            ),
            kind=(
                configs[paused_run.agent_config_id].kind
                if paused_run.agent_config_id in configs
                else "agent"
            ),
            session_id=paused_run.session_id,
            user_id=paused_run.user_id,
            requested_by=emails.get(paused_run.user_id, paused_run.user_id),
            created_at=paused_run.created_at,
            tools=[
                PendingTool(
                    tool_call_id=pending_tool.get("tool_call_id"),
                    tool_name=pending_tool.get("tool_name"),
                    tool_args=pending_tool.get("tool_args"),
                    tool_execution=pending_tool,
                )
                for pending_tool in paused_run.pending_tools or []
            ],
            steps=[PendingStep.model_validate(step) for step in paused_run.pending_steps or []],
        )
        for paused_run in runs
        if paused_run.run_id
    ]
