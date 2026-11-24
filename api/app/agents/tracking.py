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
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from agno.agent import Agent
from agno.run.agent import RunContentEvent, RunErrorEvent, RunOutput
from agno.run.base import RunStatus
from agno.run.team import RunContentEvent as TeamRunContentEvent
from agno.run.team import RunErrorEvent as TeamRunErrorEvent
from agno.run.team import TeamRunOutput
from agno.run.workflow import WorkflowErrorEvent, WorkflowRunOutput
from agno.team import Team
from agno.tools.mcp import MCPTools
from agno.workflow import Workflow
from sqlalchemy.orm import Session

from app.agents.run_cost import COST_LIMIT_MESSAGE, STOP_RUN_COST
from app.db import get_engine
from app.guardrails.input import BlockLog
from app.mcp.client import McpUnavailable, connect_strict
from app.pricing import answered_by, run_cost
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
    # no stream em primeiro plano o WorkflowPaused é montado pela rota do AgentOS depois do
    # gerador (Agno 3.1.8): aqui só passa a pausa da etapa, sem os requisitos
    "StepPaused": "paused",
    "StepOutputReview": "paused",
    "StepExecutorPaused": "paused",
    "ConditionPaused": "paused",
    "RouterPaused": "paused",
}

AnyOutput = RunOutput | TeamRunOutput
_OUTPUT_TYPES = (RunOutput, TeamRunOutput)


@dataclass
class RunRecord:
    """Desfecho de um run, gravado em agent_run e, com tokens, em usage_event."""

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
    parent_run_id: str | None = None
    eval_run_id: UUID | None = None
    pending_steps: list[dict[str, Any]] | None = None
    screened_tools: list[dict[str, Any]] | None = None
    stop_reason: str | None = None
    version_id: UUID | None = None


# run do workflow em andamento; etapas (inclusive ramos paralelos, que copiam o contexto)
# gravam esse id como pai
current_workflow_run: ContextVar[str | None] = ContextVar("current_workflow_run", default=None)


@dataclass(frozen=True)
class EvalContext:
    """Execução da suíte a que o run pertence."""

    eval_run_id: UUID
    # o runner de suíte do Agno não passa user_id: o run fica com quem disparou a suíte
    actor: str


# suíte de testes em andamento (ADR-0015): o run sai das métricas de conversa
current_eval_run: ContextVar[EvalContext | None] = ContextVar("current_eval_run", default=None)


def persist(record: RunRecord) -> None:
    """Grava o run e o consumo numa transação só; síncrono, roda fora do event loop."""
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
            parent_run_id=record.parent_run_id,
            eval_run_id=record.eval_run_id,
            pending_steps=record.pending_steps,
            screened_tools=record.screened_tools,
            stop_reason=record.stop_reason,
            version_id=record.version_id,
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
                eval_run_id=record.eval_run_id,
            )
        session.commit()


def _pending_tools(output: AnyOutput | None) -> list[dict[str, Any]] | None:
    """Tools que pausaram o run aguardando confirmação humana."""
    if output is None or output.status != RunStatus.paused:
        return None
    pending = [
        tool.to_dict()
        for tool in output.tools or []
        if tool.requires_confirmation and tool.confirmed is None
    ]
    return pending or None


def _status_of(output: AnyOutput | None, last_event: str | None) -> str:
    """Status do run pela saída do Agno ou, sem ela, pelo último evento do stream."""
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
    # versão que respondeu (ADR-0040)
    automata_version_id: UUID | None = None
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
        """Envolve a corrotina ou o stream devolvido pelo Agno com o registro do run.

        Componente montado fora da factory (sem config) e run em background, que o Agno
        devolve na hora e a fila executa depois, passam sem registro aqui.
        """
        if self.automata_config_id is None or kwargs.get("background"):
            return result
        if asyncio.iscoroutine(result):
            return self._track_output(result, kwargs)
        return self._track_stream(result, kwargs)

    def _mcp_tools(self) -> list[MCPTools]:
        """Tools MCP do próprio componente."""
        tools = self.tools if isinstance(self.tools, list) else []
        return [tool for tool in tools if isinstance(tool, MCPTools)]

    def _member_mcp_tools(self) -> list[MCPTools]:
        """Tools MCP dos membros; só o time tem."""
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
            for server_tools in [*own, *self._member_mcp_tools()]:
                await connect_strict(
                    server_tools, server_tools.tool_name_prefix or server_tools.name
                )
                connected.append(server_tools)
        except McpUnavailable:
            await _close_all(connected)
            raise
        self._mcp_tools_initialized_on_run.extend(
            server_tools for server_tools in connected if server_tools in own
        )
        return [server_tools for server_tools in connected if server_tools not in own]

    def _is_own_event(self, event: Any) -> bool:
        """Se o evento do stream é do componente, e não de um membro do time."""
        return True

    def _error_output(self, kwargs: dict[str, Any], message: str) -> AnyOutput:
        """Saída de erro montada à mão quando o MCP falha e o Agno nem chega a rodar."""
        raise NotImplementedError

    def _error_event(self, failed: AnyOutput, message: str) -> Any:
        """Evento de erro equivalente a `_error_output`, para o stream."""
        raise NotImplementedError

    async def _track_output(self, coro: Any, kwargs: dict[str, Any]) -> Any:
        """Run sem stream: aguarda a saída e grava o desfecho, inclusive erro e cancelamento."""
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
        if isinstance(output, _OUTPUT_TYPES) and self._stopped_by_cost() and not output.content:
            # o Agno não chama o modelo depois do StopAgentRun: a resposta viria vazia
            output.content = COST_LIMIT_MESSAGE
        if isinstance(output, _OUTPUT_TYPES):
            record = self._record(kwargs, start, output, output.run_id, None, None)
            await self._save(record)
            self._fail_step(record)
        return output

    async def _track_stream(self, stream: AsyncIterator[Any], kwargs: dict[str, Any]) -> Any:
        """Run em stream: repassa cada evento e grava o desfecho quando o stream acaba."""
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
        except asyncio.CancelledError, GeneratorExit:
            self._schedule(self._record(kwargs, start, output, run_id, "cancelled", None))
            raise
        except Exception as exc:
            await self._save(self._record(kwargs, start, output, run_id, "error", str(exc)))
            raise
        finally:
            await _close_all(members)
        # stream sem o RunOutput no fim: a saída vem do que o Agno gravou na sessão
        if output is None and run_id and session_id:
            try:
                output = await self.aget_run_output(  # type: ignore[attr-defined]
                    run_id=run_id, session_id=session_id
                )
            except Exception:
                logger.warning("run sem saída persistida", extra={"run_id": run_id})
        if self._stopped_by_cost() and run_id:
            yield self._notice_event(run_id, session_id, COST_LIMIT_MESSAGE)
        status = _status_of(output, last_event)
        record = self._record(kwargs, start, output, run_id, status, None)
        await self._save(record)
        self._fail_step(record)

    def _stopped_by_cost(self) -> bool:
        """Se o teto de custo (ADR-0031) parou este run."""
        blocks = self.automata_blocks
        return blocks is not None and blocks.stop_reason == STOP_RUN_COST

    def _notice_event(self, run_id: str, session_id: str | None, message: str) -> Any:
        """Evento de conteúdo com um aviso do app, no formato do componente."""
        raise NotImplementedError

    def _fail_step(self, record: RunRecord) -> None:
        """Em etapa de workflow, relança erro ou bloqueio como `StepFailed`."""
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
        """Monta o registro do run; `status` None deixa o status sair da saída do Agno."""
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
        evaluation = current_eval_run.get()
        return RunRecord(
            agent_config_id=self.automata_config_id,
            version_id=self.automata_version_id,
            # com reserva, o modelo que respondeu (ADR-0027)
            model_id=answered_by(metrics, self.automata_model_id),
            user_id=kwargs.get("user_id")
            or (evaluation.actor if evaluation else None)
            or "anonymous",
            run_id=run_id or (output.run_id if output is not None else None),
            status=final_status,
            duration_ms=int((duration if duration is not None else monotonic() - start) * 1000),
            error=error,
            input_tokens=int(getattr(metrics, "input_tokens", 0) or 0),
            output_tokens=int(getattr(metrics, "output_tokens", 0) or 0),
            total_tokens=int(getattr(metrics, "total_tokens", 0) or 0),
            # Anthropic e OpenAI não informam custo: tabela por modelo (ADR-0021, ADR-0027)
            cost=run_cost(metrics, self.automata_model_id),
            session_id=kwargs.get("session_id") or (output.session_id if output else None),
            pending_tools=_pending_tools(output),
            parent_run_id=current_workflow_run.get(),
            eval_run_id=evaluation.eval_run_id if evaluation else None,
            blocked_by=block.rule if final_status == "blocked" and block else None,
            block_detail=block.detail if final_status == "blocked" and block else None,
            screened_tools=list(self.automata_blocks.screened)
            if self.automata_blocks is not None and self.automata_blocks.screened
            else None,
            stop_reason=self.automata_blocks.stop_reason
            if self.automata_blocks is not None
            else None,
        )

    @staticmethod
    async def _save(record: RunRecord) -> None:
        """Grava fora do event loop; falha de banco vira log e não derruba a resposta."""
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
    """Fecha as conexões MCP ignorando erro: o fechamento não muda o desfecho do run."""
    for server_tools in tools:
        with contextlib.suppress(Exception):
            await server_tools.close()


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

    def _notice_event(self, run_id: str, session_id: str | None, message: str) -> Any:
        return RunContentEvent(
            run_id=run_id, agent_id=self.id or "", session_id=session_id, content=message
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
            result.extend(tool for tool in tools if isinstance(tool, MCPTools))
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

    def _notice_event(self, run_id: str, session_id: str | None, message: str) -> Any:
        return TeamRunContentEvent(
            run_id=run_id, team_id=self.id or "", session_id=session_id, content=message
        )

    def _error_event(self, failed: AnyOutput, message: str) -> Any:
        return TeamRunErrorEvent(
            run_id=failed.run_id,
            team_id=self.id or "",
            session_id=failed.session_id,
            content=message,
            error_type="mcp_unavailable",
        )


# saída da etapa mostrada na página Aprovações; o resto fica no run do Agno
PENDING_OUTPUT_CHARS = 4000


def pending_steps(requirements: list[Any] | None) -> list[dict[str, Any]] | None:
    """Resumo dos requisitos ativos do workflow pausado (ADR-0023)."""
    active = [
        requirement
        for requirement in requirements or []
        if not getattr(requirement, "is_resolved", False)
    ]
    if not active:
        return None
    summaries: list[dict[str, Any]] = []
    for requirement in active:
        reviews_output = bool(getattr(requirement, "requires_output_review", False))
        # revisão da volta de laço (ADR-0028): a saída é a da volta que acabou
        is_loop_review = getattr(requirement, "step_type", None) == "Loop"
        step_output = getattr(requirement, "step_output", None)
        content = getattr(step_output, "content", None) if step_output is not None else None
        timeout_at = getattr(requirement, "timeout_at", None)
        summaries.append(
            {
                "step_id": requirement.step_id,
                "step_name": requirement.step_name,
                "when": "loop" if is_loop_review else "after" if reviews_output else "before",
                "message": (
                    requirement.output_review_message
                    if reviews_output
                    else requirement.confirmation_message
                )
                or None,
                "output": str(content)[:PENDING_OUTPUT_CHARS]
                if reviews_output and content
                else None,
                "timeout_at": timeout_at.isoformat() if timeout_at else None,
                "retry_count": getattr(requirement, "retry_count", 0),
            }
        )
    return summaries


class TrackedWorkflow(Workflow):
    """Workflow que registra o próprio run e transforma etapa que parou em run com erro.

    Com on_error=fail o Agno relança a exceção da etapa sem gravar o run, e a rota
    responde 500. Aqui a falha vira WorkflowRunOutput(status=ERROR) ou WorkflowErrorEvent
    no stream, e o run vai para agent_run com a duração e o motivo (ADR-0014).
    """

    automata_config_id: UUID | None = None

    def arun(self, *args: Any, **kwargs: Any) -> Any:
        if self.automata_config_id is None or kwargs.get("background"):
            return super().arun(*args, **kwargs)
        # run_id definido aqui: as etapas precisam dele como pai antes de o Agno gerá-lo
        kwargs["run_id"] = kwargs.get("run_id") or str(uuid4())
        result = super().arun(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return self._track_output(result, kwargs)
        return self._track_stream(result, kwargs)

    async def acontinue_run(self, *args: Any, **kwargs: Any) -> Any:
        """Continue depois da revisão humana: atualiza o mesmo agent_run (ADR-0023)."""
        if self.automata_config_id is None:
            return await super().acontinue_run(*args, **kwargs)
        paused = kwargs.get("run_response")
        run_id = kwargs.get("run_id") or getattr(paused, "run_id", None)
        if run_id is not None:
            # antes de retomar, ainda no contexto da request que sabe quem decidiu: a
            # decisão vale mesmo que o resto falhe ou que o run siga na fila (ADR-0028)
            await self._record_reviews(run_id, kwargs.get("step_requirements"))
        if kwargs.get("background"):
            return await super().acontinue_run(*args, **kwargs)
        track = {**kwargs, "run_id": run_id}
        if kwargs.get("stream"):
            return self._track_stream(await super().acontinue_run(*args, **kwargs), track)
        return await self._track_output(super().acontinue_run(*args, **kwargs), track)

    @staticmethod
    async def _record_reviews(run_id: str, requirements: list[Any] | None) -> None:
        """Grava as decisões humanas do continue com quem decidiu (ADR-0028)."""
        from app.agents.reviews import record_reviews
        from app.integrations import current_actor

        try:
            await asyncio.to_thread(record_reviews, run_id, requirements, current_actor.get())
        except Exception as exc:
            # sem banco o registro se perde, mas a decisão de quem aprovou segue
            detail = {"run_id": run_id, "error": str(exc)}
            logger.warning("falha ao registrar a revisão", extra=detail)

    def _record(
        self,
        kwargs: dict[str, Any],
        start: float,
        output: WorkflowRunOutput | None,
        run_id: str | None,
        status: str,
        error: str | None,
        pending: list[dict[str, Any]] | None = None,
    ) -> RunRecord:
        """Registro do run do workflow: sem modelo nem tokens, que ficam nas etapas."""
        assert self.automata_config_id is not None
        # caso da suíte (ADR-0022): o run do workflow fica fora das conversas, como as etapas
        evaluation = current_eval_run.get()
        return RunRecord(
            agent_config_id=self.automata_config_id,
            model_id="",
            user_id=kwargs.get("user_id") or self.user_id or "anonymous",
            run_id=run_id or (output.run_id if output is not None else None),
            status=status,
            duration_ms=int((monotonic() - start) * 1000),
            error=error,
            session_id=kwargs.get("session_id") or (output.session_id if output else None),
            eval_run_id=evaluation.eval_run_id if evaluation else None,
            pending_steps=pending if status == "paused" else None,
        )

    def _failed(
        self, kwargs: dict[str, Any], run_id: str | None, message: str
    ) -> WorkflowRunOutput:
        """Saída com erro no lugar da exceção que o Agno relançaria."""
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
        """Workflow sem stream, com o run_id no contexto para as etapas se ligarem a ele."""
        start = monotonic()
        token = current_workflow_run.set(kwargs["run_id"])
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
        finally:
            current_workflow_run.reset(token)
        status = _STATUS.get(output.status, "success") if output.status else "success"
        error = str(output.content) if status == "error" and output.content else None
        pending = pending_steps(output.step_requirements) if status == "paused" else None
        await RunTracking._save(
            self._record(kwargs, start, output, output.run_id, status, error, pending)
        )
        return output

    async def _track_stream(self, stream: AsyncIterator[Any], kwargs: dict[str, Any]) -> Any:
        """Workflow em stream: o desfecho sai do último evento de fim ou de pausa."""
        start = monotonic()
        run_id: str | None = kwargs.get("run_id")
        last_event: str | None = None
        error: str | None = None
        pending: list[dict[str, Any]] | None = None
        # gerador: o contexto vale enquanto ele é iterado, na task de quem consome o stream
        current_workflow_run.set(run_id)
        try:
            async for event in stream:
                run_id = getattr(event, "run_id", None) or run_id
                event_name = getattr(event, "event", None)
                if event_name in _WORKFLOW_END_EVENTS:
                    last_event = event_name
                    error = getattr(event, "error", None) or error
                elif (
                    event_name == "StepStarted"
                    and _WORKFLOW_END_EVENTS.get(last_event or "") == "paused"
                ):
                    # pausa da etapa já decidida no mesmo stream: o fluxo seguiu
                    last_event = None
                if event_name == "WorkflowPaused":
                    pending = pending_steps(getattr(event, "step_requirements", None))
                yield event
        except asyncio.CancelledError, GeneratorExit:
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
        # pausa vista só pela etapa: os requisitos vêm do run que o Agno gravou
        if status == "paused" and pending is None and run_id is not None:
            pending = await self._pending_from_db(run_id, kwargs.get("session_id"))
        await RunTracking._save(self._record(kwargs, start, None, run_id, status, error, pending))

    async def _pending_from_db(
        self, run_id: str, session_id: str | None
    ) -> list[dict[str, Any]] | None:
        """Pendências do workflow pausado lidas do run gravado; falha de leitura dá None."""
        try:
            paused = await self.aget_run_output(run_id, session_id=session_id)

        except Exception as exc:
            logger.warning("pausa sem requisitos", extra={"run_id": run_id, "error": str(exc)})
            return None
        return pending_steps(paused.step_requirements) if paused is not None else None
