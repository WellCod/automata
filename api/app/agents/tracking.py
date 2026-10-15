"""Registro de execução e consumo por run.

Post-hooks do Agno só rodam quando o run termina bem: erro e cancelamento
nunca chegavam ao agent_run. O TrackedAgent envolve arun/acontinue_run e
grava o desfecho real (status, duração, erro, tokens) numa transação só,
fora do event loop.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any
from uuid import UUID

from agno.agent import Agent
from agno.run.agent import RunOutput
from agno.run.base import RunStatus
from sqlalchemy.orm import Session

from app.db import get_engine
from app.repositories.run import RunRepository
from app.repositories.usage import UsageRepository

logger = logging.getLogger(__name__)

_STATUS = {
    RunStatus.completed: "success",
    RunStatus.error: "error",
    RunStatus.cancelled: "cancelled",
    RunStatus.paused: "paused",
}

_ERROR_EVENTS = {"RunError"}
_CANCELLED_EVENTS = {"RunCancelled"}
_PAUSED_EVENTS = {"RunPaused"}


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


def persist(record: RunRecord) -> None:
    with Session(get_engine()) as session:
        RunRepository(session).upsert(
            agent_config_id=record.agent_config_id,
            user_id=record.user_id,
            run_id=record.run_id,
            status=record.status,
            duration_ms=record.duration_ms,
            error=record.error,
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


def _status_of(output: RunOutput | None, last_event: str | None) -> str:
    if output is not None and output.status in _STATUS:
        return _STATUS[output.status]
    if last_event in _ERROR_EVENTS:
        return "error"
    if last_event in _CANCELLED_EVENTS:
        return "cancelled"
    if last_event in _PAUSED_EVENTS:
        return "paused"
    return "success"


class TrackedAgent(Agent):
    """Agent que registra o desfecho de cada run em agent_run e usage_event."""

    automata_config_id: UUID | None = None
    automata_model_id: str = ""

    def arun(self, *args: Any, **kwargs: Any) -> Any:
        result = super().arun(*args, **kwargs)
        return self._track(result, kwargs)

    def acontinue_run(self, *args: Any, **kwargs: Any) -> Any:
        result = super().acontinue_run(*args, **kwargs)
        return self._track(result, kwargs)

    def _track(self, result: Any, kwargs: dict[str, Any]) -> Any:
        if self.automata_config_id is None or kwargs.get("background"):
            return result
        if asyncio.iscoroutine(result):
            return self._track_output(result, kwargs)
        return self._track_stream(result, kwargs)

    async def _track_output(self, coro: Any, kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        try:
            output = await coro
        except asyncio.CancelledError:
            self._schedule(self._record(kwargs, start, None, None, "cancelled", None))
            raise
        except Exception as exc:
            await self._save(self._record(kwargs, start, None, None, "error", str(exc)))
            raise
        if isinstance(output, RunOutput):
            await self._save(self._record(kwargs, start, output, output.run_id, None, None))
        return output

    async def _track_stream(self, stream: AsyncIterator[Any], kwargs: dict[str, Any]) -> Any:
        start = monotonic()
        run_id: str | None = kwargs.get("run_id")
        session_id: str | None = kwargs.get("session_id")
        last_event: str | None = None
        output: RunOutput | None = None
        try:
            async for event in stream:
                run_id = getattr(event, "run_id", None) or run_id
                session_id = getattr(event, "session_id", None) or session_id
                last_event = getattr(event, "event", None) or last_event
                if isinstance(event, RunOutput):
                    output = event
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            self._schedule(self._record(kwargs, start, output, run_id, "cancelled", None))
            raise
        except Exception as exc:
            await self._save(self._record(kwargs, start, output, run_id, "error", str(exc)))
            raise
        if output is None and run_id and session_id:
            try:
                output = await self.aget_run_output(run_id=run_id, session_id=session_id)
            except Exception:
                logger.warning("run sem saída persistida", extra={"run_id": run_id})
        status = _status_of(output, last_event)
        await self._save(self._record(kwargs, start, output, run_id, status, None))

    def _record(
        self,
        kwargs: dict[str, Any],
        start: float,
        output: RunOutput | None,
        run_id: str | None,
        status: str | None,
        error: str | None,
    ) -> RunRecord:
        assert self.automata_config_id is not None
        final_status = status or _status_of(output, None)
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
