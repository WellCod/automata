"""Registro de execução e consumo por run.

Post-hooks do Agno só rodam quando o run termina bem: erro e cancelamento
nunca chegavam ao agent_run. TrackedAgent e TrackedTeam envolvem
arun/acontinue_run e gravam o desfecho real (status, duração, erro, tokens)
numa transação só, fora do event loop.

Em time, só o run do time é gravado: o consumo dele já soma os membros, e
gravar os membros também duplicaria o custo no analytics (ADR-0011).
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from agno.agent import Agent
from agno.run.agent import RunErrorEvent, RunOutput
from agno.run.base import RunStatus
from agno.run.team import RunErrorEvent as TeamRunErrorEvent
from agno.run.team import TeamRunOutput
from agno.run.workflow import WorkflowErrorEvent, WorkflowRunOutput
from agno.team import Team
from agno.tools.mcp import MCPTools
from agno.workflow import Workflow
from sqlalchemy.orm import Session

from app.db import get_engine
from app.guardrails.input import BlockLog
from app.mcp.client import McpUnavailable, connect_strict
from app.repositories.run import RunRepository
from app.repositories.usage import UsageRepository

logger = logging.getLogger(__name__)

_STATUS = {
    RunStatus.completed: "success",
    RunStatus.error: "error",
    RunStatus.cancelled: "cancelled",
    RunStatus.paused: "paused",
}

_ERROR_EVENTS = {"RunError", "TeamRunError"}
_CANCELLED_EVENTS = {"RunCancelled", "TeamRunCancelled"}
_PAUSED_EVENTS = {"RunPaused", "TeamRunPaused"}

_WORKFLOW_END_EVENTS = {
    "WorkflowCompleted": "success",
    "WorkflowError": "error",
    "WorkflowCancelled": "cancelled",
    "WorkflowPaused": "paused",
}

AnyOutput = RunOutput | TeamRunOutput
_OUTPUT_TYPES = (RunOutput, TeamRunOutput)


@dataclass
class RunRecord:
    agent_config_id: UUID
    model_id: str
    user_id: str
    run_id: str | None
    status: str
    duration_ms: int
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float | None = None
    session_id: str | None = None
    pending_tools: list[dict[str, Any]] | None = None
    blocked_by: str | None = None
    block_detail: dict[str, Any] | None = None


def persist(record: RunRecord) -> None:
    with Session(get_engine()) as session:
        RunRepository(session).upsert(
            agent_config_id=record.agent_config_id,
            user_id=record.user_id,
            run_id=record.run_id,
            status=record.status,
            duration_ms=record.duration_ms,
            error=record.error,
            session_id=record.session_id,
            pending_tools=record.pending_tools,
            blocked_by=record.blocked_by,
            block_detail=record.block_detail,
        )
        if record.total_tokens:
            UsageRepository(session).record_event(
                agent_config_id=record.agent_config_id,
                user_id=record.user_id,
                run_id=record.run_id,
                model_id=record.model_id,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                total_tokens=record.total_tokens,
                cost=record.cost,
                period=datetime.now(UTC).strftime("%Y%m"),
            )
        session.commit()


def _pending_tools(output: AnyOutput | None) -> list[dict[str, Any]] | None:
    """Tools que pausaram o run aguardando confirmação humana."""
    if output is None or output.status != RunStatus.paused:
        return None
    pending = [
        t.to_dict() for t in output.tools or [] if t.requires_confirmation and t.confirmed is None
    ]
    return pending or None


def _status_of(output: AnyOutput | None, last_event: str | None) -> str:
    if output is not None and output.status in _STATUS:
        return _STATUS[output.status]
    if last_event in _ERROR_EVENTS:
        return "error"
    if last_event in _CANCELLED_EVENTS:
        return "cancelled"
    if last_event in _PAUSED_EVENTS:
        return "paused"
    return "success"


class StepFailed(RuntimeError):
    """Etapa de workflow terminou em erro ou bloqueio (ADR-0014)."""


class RunTracking:
    """Registro de run e conexão estrita de MCP, comum a agente e time.

    Mixin: vem antes de Agent/Team na herança, e `super().arun` cai no Agno.
    """

    automata_config_id: UUID | None = None
    automata_model_id: str = ""
    # preenchido pelos guardrails de entrada da factory
    automata_blocks: BlockLog | None = None
    # em etapa de workflow: erro ou bloqueio vira exceção, para o on_error do Agno valer
    automata_raise_on_error: bool = False
    tools: Any
    id: Any
    name: Any
    _mcp_tools_initialized_on_run: Any

    def arun(self, *args: Any, **kwargs: Any) -> Any:
        result = super().arun(*args, **kwargs)  # type: ignore[misc]
        return self._track(result, kwargs)

    def acontinue_run(self, *args: Any, **kwargs: Any) -> Any:
        result = super().acontinue_run(*args, **kwargs)  # type: ignore[misc]
        return self._track(result, kwargs)

    def _track(self, result: Any, kwargs: dict[str, Any]) -> Any:
        if self.automata_config_id is None or kwargs.get("background"):
            return result
        if asyncio.iscoroutine(result):
            return self._track_output(result, kwargs)
        return self._track_stream(result, kwargs)

    def _mcp_tools(self) -> list[MCPTools]:
        tools = self.tools if isinstance(self.tools, list) else []
        return [t for t in tools if isinstance(t, MCPTools)]

    def _member_mcp_tools(self) -> list[MCPTools]:
        return []

    async def _connect_mcp(self) -> list[MCPTools]:
        """Conecta os servidores MCP antes do run, falhando alto (ADR-0010).

        Roda na mesma task que o run do Agno. As tools do próprio componente
        entram em _mcp_tools_initialized_on_run, e o Agno as fecha no finally
        do run. As dos membros de time ficam abertas entre delegações e são
        devolvidas para o wrapper fechar ao fim, na mesma task.
        """
        connected: list[MCPTools] = []
        own = self._mcp_tools()
        try:
            for tools in [*own, *self._member_mcp_tools()]:
                await connect_strict(tools, tools.tool_name_prefix or tools.name)
                connected.append(tools)
        except McpUnavailable:
            await _close_all(connected)
            raise
        self._mcp_tools_initialized_on_run.extend(t for t in connected if t in own)
        return [t for t in connected if t not in own]

    def _is_own_event(self, event: Any) -> bool:
        return True

    def _error_output(self, kwargs: dict[str, Any], message: str) -> AnyOutput:
        raise NotImplementedError

    def _error_event(self, failed: AnyOutput, message: str) -> Any:
        raise NotImplementedError

    async def _track_output(self, coro: Any, kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        try:
            members = await self._connect_mcp()
        except McpUnavailable as exc:
            coro.close()
            output = self._error_output(kwargs, str(exc))
            record = self._record(kwargs, start, output, output.run_id, "error", str(exc))
            await self._save(record)
            self._fail_step(record)
            return output
        try:
            output = await coro
        except asyncio.CancelledError:
            self._schedule(self._record(kwargs, start, None, None, "cancelled", None))
            raise
        except Exception as exc:
            await self._save(self._record(kwargs, start, None, None, "error", str(exc)))
            raise
        finally:
            await _close_all(members)
        if isinstance(output, _OUTPUT_TYPES):
            record = self._record(kwargs, start, output, output.run_id, None, None)
            await self._save(record)
            self._fail_step(record)
        return output

    async def _track_stream(self, stream: AsyncIterator[Any], kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        run_id: str | None = kwargs.get("run_id")
        session_id: str | None = kwargs.get("session_id")
        last_event: str | None = None
        output: AnyOutput | None = None
        try:
            members = await self._connect_mcp()
        except McpUnavailable as exc:
            await stream.aclose()  # type: ignore[attr-defined]
            failed = self._error_output(kwargs, str(exc))
            yield self._error_event(failed, str(exc))
            record = self._record(kwargs, start, failed, failed.run_id, "error", str(exc))
            await self._save(record)
            self._fail_step(record)
            return
        try:
            async for event in stream:
                run_id = getattr(event, "run_id", None) or run_id
                session_id = getattr(event, "session_id", None) or session_id
                # eventos de membro chegam no mesmo stream; o desfecho é o do componente
                if self._is_own_event(event):
                    last_event = getattr(event, "event", None) or last_event
                if isinstance(event, _OUTPUT_TYPES):
                    output = event
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            self._schedule(self._record(kwargs, start, output, run_id, "cancelled", None))
            raise
        except Exception as exc:
            await self._save(self._record(kwargs, start, output, run_id, "error", str(exc)))
            raise
        finally:
            await _close_all(members)
        if output is None and run_id and session_id:
            try:
                output = await self.aget_run_output(  # type: ignore[attr-defined]
                    run_id=run_id, session_id=session_id
                )
            except Exception:
                logger.warning("run sem saída persistida", extra={"run_id": run_id})
        status = _status_of(output, last_event)
        record = self._record(kwargs, start, output, run_id, status, None)
        await self._save(record)
        self._fail_step(record)

    def _fail_step(self, record: RunRecord) -> None:
        # No Agno, etapa cujo agente falha segue e passa o erro como entrada da próxima
        if self.automata_raise_on_error and record.status in ("error", "blocked"):
            raise StepFailed(record.error or record.status)

    def _record(
        self,
        kwargs: dict[str, Any],
        start: float,
        output: AnyOutput | None,
        run_id: str | None,
        status: str | None,
        error: str | None,
    ) -> RunRecord:
        assert self.automata_config_id is not None
        final_status = status or _status_of(output, None)
        block = self.automata_blocks.last if self.automata_blocks is not None else None
        if final_status == "error" and block is not None:
            # guardrail barrou: não é falha do agente e não entra na taxa de erro
            final_status, error = "blocked", block.message
        if final_status == "error" and error is None and output is not None:
            error = str(output.content) if output.content is not None else None
        metrics = output.metrics if output is not None else None
        duration = getattr(metrics, "duration", None)
        return RunRecord(
            agent_config_id=self.automata_config_id,
            model_id=self.automata_model_id,
            user_id=kwargs.get("user_id") or "anonymous",
            run_id=run_id or (output.run_id if output is not None else None),
            status=final_status,
            duration_ms=int((duration if duration is not None else monotonic() - start) * 1000),
            error=error,
            input_tokens=int(getattr(metrics, "input_tokens", 0) or 0),
            output_tokens=int(getattr(metrics, "output_tokens", 0) or 0),
            total_tokens=int(getattr(metrics, "total_tokens", 0) or 0),
            cost=getattr(metrics, "cost", None),
            session_id=kwargs.get("session_id") or (output.session_id if output else None),
            pending_tools=_pending_tools(output),
            blocked_by=block.rule if final_status == "blocked" and block else None,
            block_detail=block.detail if final_status == "blocked" and block else None,
        )

    @staticmethod
    async def _save(record: RunRecord) -> None:
        try:
            await asyncio.to_thread(persist, record)
        except Exception as exc:
            logger.error("falha ao registrar run", extra={"error": str(exc)})

    @staticmethod
    def _schedule(record: RunRecord) -> None:
        # Durante cancelamento não dá para aguardar: grava em thread sem bloquear
        try:
            asyncio.get_running_loop().run_in_executor(None, persist, record)
        except RuntimeError:
            persist(record)


async def _close_all(tools: list[MCPTools]) -> None:
    for t in tools:
        with contextlib.suppress(Exception):
            await t.close()


class TrackedAgent(RunTracking, Agent):
    """Agent que registra o desfecho de cada run em agent_run e usage_event."""

    def _error_output(self, kwargs: dict[str, Any], message: str) -> AnyOutput:
        return RunOutput(
            run_id=kwargs.get("run_id") or str(uuid4()),
            agent_id=self.id,
            agent_name=self.name,
            session_id=kwargs.get("session_id"),
            user_id=kwargs.get("user_id"),
            content=message,
            status=RunStatus.error,
        )

    def _error_event(self, failed: AnyOutput, message: str) -> Any:
        return RunErrorEvent(
            run_id=failed.run_id,
            agent_id=self.id or "",
            session_id=failed.session_id,
            content=message,
            error_type="mcp_unavailable",
        )


class TrackedTeam(RunTracking, Team):
    """Team que registra o run do time; conecta também o MCP dos membros."""

    def _member_mcp_tools(self) -> list[MCPTools]:
        members = self.members if isinstance(self.members, list) else []
        result: list[MCPTools] = []
        for member in members:
            tools = member.tools if isinstance(member.tools, list) else []
            result.extend(t for t in tools if isinstance(t, MCPTools))
        return result

    def _is_own_event(self, event: Any) -> bool:
        # evento de membro carrega agent_id; o do time, team_id
        return getattr(event, "agent_id", None) in (None, "")

    def _error_output(self, kwargs: dict[str, Any], message: str) -> AnyOutput:
        return TeamRunOutput(
            run_id=kwargs.get("run_id") or str(uuid4()),
            team_id=self.id,
            team_name=self.name,
            session_id=kwargs.get("session_id"),
            user_id=kwargs.get("user_id"),
            content=message,
            status=RunStatus.error,
        )

    def _error_event(self, failed: AnyOutput, message: str) -> Any:
        return TeamRunErrorEvent(
            run_id=failed.run_id,
            team_id=self.id or "",
            session_id=failed.session_id,
            content=message,
            error_type="mcp_unavailable",
        )


class TrackedWorkflow(Workflow):
    """Workflow que registra o próprio run e transforma etapa que parou em run com erro.

    Com on_error=fail o Agno relança a exceção da etapa sem gravar o run, e a rota
    responde 500. Aqui a falha vira WorkflowRunOutput(status=ERROR) ou WorkflowErrorEvent
    no stream, e o run vai para agent_run com a duração e o motivo (ADR-0014).
    """

    automata_config_id: UUID | None = None

    def arun(self, *args: Any, **kwargs: Any) -> Any:
        result = super().arun(*args, **kwargs)
        if self.automata_config_id is None or kwargs.get("background"):
            return result
        if asyncio.iscoroutine(result):
            return self._track_output(result, kwargs)
        return self._track_stream(result, kwargs)

    def _record(
        self,
        kwargs: dict[str, Any],
        start: float,
        output: WorkflowRunOutput | None,
        run_id: str | None,
        status: str,
        error: str | None,
    ) -> RunRecord:
        assert self.automata_config_id is not None
        return RunRecord(
            agent_config_id=self.automata_config_id,
            model_id="",
            user_id=kwargs.get("user_id") or self.user_id or "anonymous",
            run_id=run_id or (output.run_id if output is not None else None),
            status=status,
            duration_ms=int((monotonic() - start) * 1000),
            error=error,
            session_id=kwargs.get("session_id") or (output.session_id if output else None),
        )

    def _failed(
        self, kwargs: dict[str, Any], run_id: str | None, message: str
    ) -> WorkflowRunOutput:
        return WorkflowRunOutput(
            run_id=run_id or kwargs.get("run_id") or str(uuid4()),
            workflow_id=self.id,
            workflow_name=self.name,
            session_id=kwargs.get("session_id"),
            user_id=kwargs.get("user_id") or self.user_id,
            content=message,
            status=RunStatus.error,
        )

    async def _track_output(self, coro: Any, kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        try:
            output = await coro
        except asyncio.CancelledError:
            RunTracking._schedule(self._record(kwargs, start, None, None, "cancelled", None))
            raise
        except Exception as exc:
            failed = self._failed(kwargs, None, str(exc))
            await RunTracking._save(
                self._record(kwargs, start, failed, failed.run_id, "error", str(exc))
            )
            return failed
        status = _STATUS.get(output.status, "success") if output.status else "success"
        error = str(output.content) if status == "error" and output.content else None
        await RunTracking._save(self._record(kwargs, start, output, output.run_id, status, error))
        return output

    async def _track_stream(self, stream: AsyncIterator[Any], kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        run_id: str | None = kwargs.get("run_id")
        last_event: str | None = None
        error: str | None = None
        try:
            async for event in stream:
                run_id = getattr(event, "run_id", None) or run_id
                name = getattr(event, "event", None)
                if name in _WORKFLOW_END_EVENTS:
                    last_event = name
                    error = getattr(event, "error", None) or error
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            RunTracking._schedule(self._record(kwargs, start, None, run_id, "cancelled", None))
            raise
        except Exception as exc:
            yield WorkflowErrorEvent(
                workflow_id=self.id,
                run_id=run_id,
                session_id=kwargs.get("session_id"),
                error=str(exc),
                error_type="step_failed",
            )
            await RunTracking._save(self._record(kwargs, start, None, run_id, "error", str(exc)))
            return
        status = _WORKFLOW_END_EVENTS.get(last_event or "", "success")
        await RunTracking._save(self._record(kwargs, start, None, run_id, status, error))
