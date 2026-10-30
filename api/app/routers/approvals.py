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
    # before: confirma antes de rodar; after: aprova a saída antes da próxima etapa
    when: Literal["before", "after"]
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
    created_at: datetime
    tools: list[PendingTool]
    steps: list[PendingStep]


@router.get("", response_model=list[ApprovalItem])
def list_pending(
    request: Request,
    session: SessionDep,
    agent_id: UUID | None = Query(default=None),  # noqa: B008
) -> list[ApprovalItem]:
    # a pendência traz argumentos de tool e saída de etapa, que são dados da conversa:
    # cada um vê as suas, o owner vê todas (o continue do Agno também exige o dono)
    user_id = None if sees_everyone(request) else str(getattr(request.state, "user_id", ""))
    runs = RunRepository(session).list_paused([agent_id] if agent_id else None, user_id=user_id)
    ids = list({r.agent_config_id for r in runs})
    configs = {c.id: c for c in session.scalars(select(AgentConfig).where(AgentConfig.id.in_(ids)))}
    return [
        ApprovalItem(
            run_id=r.run_id or "",
            agent_id=r.agent_config_id,
            agent_name=configs[r.agent_config_id].name if r.agent_config_id in configs else "",
            kind=configs[r.agent_config_id].kind if r.agent_config_id in configs else "agent",
            session_id=r.session_id,
            user_id=r.user_id,
            created_at=r.created_at,
            tools=[
                PendingTool(
                    tool_call_id=t.get("tool_call_id"),
                    tool_name=t.get("tool_name"),
                    tool_args=t.get("tool_args"),
                    tool_execution=t,
                )
                for t in r.pending_tools or []
            ],
            steps=[PendingStep.model_validate(step) for step in r.pending_steps or []],
        )
        for r in runs
        if r.run_id
    ]
