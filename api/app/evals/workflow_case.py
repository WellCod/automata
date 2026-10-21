"""Workflow no lugar do `agent=` do `Case` do Agno (ADR-0022).

O runner de suíte só aceita agente ou time, mas só confere que o campo está
preenchido e chama `arun` com stream, esperando um `RunOutput` no fim. O
adaptador roda o workflow sem stream e devolve um `RunOutput` com a saída final
e as etapas que rodaram em `metadata`, para o scorer conferir o caminho. Juiz,
timeout e o resultado caso a caso continuam do runner do Agno.
"""

from collections.abc import AsyncIterator, Iterable
from typing import Any

from agno.run.agent import RunOutput
from agno.run.base import RunStatus
from agno.run.workflow import WorkflowErrorEvent, WorkflowRunOutput
from agno.workflow import StepOutput

from app.agents.tracking import TrackedWorkflow


def steps_run(output: WorkflowRunOutput, known: set[str]) -> list[str]:
    """Etapas que rodaram, na ordem, sem os contêineres (paralelo, condição, laço)."""
    names: list[str] = []

    def walk(items: Iterable[Any]) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item)
                continue
            if not isinstance(item, StepOutput):
                continue
            if item.step_name in known:
                names.append(item.step_name)
            walk(item.steps or [])

    walk(output.step_results or [])
    return names


class WorkflowUnderTest:
    def __init__(self, workflow: TrackedWorkflow, step_names: set[str]) -> None:
        self.workflow = workflow
        self.id = workflow.id
        self.name = workflow.name
        self._known = step_names

    async def arun(
        self,
        input: Any,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
        **_: Any,
    ) -> AsyncIterator[Any]:
        output: WorkflowRunOutput = await self.workflow.arun(
            input=input, session_id=session_id, user_id=user_id, stream=False
        )
        if output.status == RunStatus.error:
            # evento de erro: o runner do Agno grava o motivo em vez de "sem saída"
            yield WorkflowErrorEvent(
                workflow_id=self.id,
                run_id=output.run_id,
                session_id=session_id,
                error=str(output.content or "etapa parou o workflow"),
            )
            return
        yield RunOutput(
            run_id=output.run_id,
            agent_id=self.id,
            session_id=session_id,
            content=output.content,
            status=output.status or RunStatus.completed,
            metadata={"steps": steps_run(output, self._known)},
        )
