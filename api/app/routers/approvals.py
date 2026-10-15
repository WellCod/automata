"""Runs pausados aguardando confirmação humana de tools.

A decisão em si é feita na rota do AgentOS
(`POST /agents/{id}/runs/{run_id}/continue`), reenviando cada item de
`tool_execution` com `confirmed` true ou false; aqui só se lista o pendente.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.repositories.config import ConfigRepository
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


class ApprovalItem(BaseModel):
    run_id: str
    agent_id: UUID
    agent_name: str
    session_id: str | None
    user_id: str
    created_at: datetime
    tools: list[PendingTool]


@router.get("", response_model=list[ApprovalItem])
def list_pending(
    session: SessionDep,
    agent_id: UUID | None = Query(default=None),  # noqa: B008
) -> list[ApprovalItem]:
    runs = RunRepository(session).list_paused([agent_id] if agent_id else None)
    names = ConfigRepository(session).names_by_ids(list({r.agent_config_id for r in runs}))
    return [
        ApprovalItem(
            run_id=r.run_id or "",
            agent_id=r.agent_config_id,
            agent_name=names.get(r.agent_config_id, ""),
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
        )
        for r in runs
        if r.run_id
    ]
