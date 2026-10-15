"""Registro de runs pelo TrackedAgent: sucesso, erro, com e sem stream."""

import uuid
from typing import Any

import pytest
from agno.models.response import ModelResponse

from app.agents import tracking
from app.agents.replay import ReplayModel
from app.agents.tracking import RunRecord, TrackedAgent


class FailingModel(ReplayModel):
    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise RuntimeError("provedor fora do ar")

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provedor fora do ar")
        yield  # pragma: no cover


@pytest.fixture
def records(monkeypatch: pytest.MonkeyPatch) -> list[RunRecord]:
    saved: list[RunRecord] = []
    monkeypatch.setattr(tracking, "persist", saved.append)
    return saved


def _agent(model: ReplayModel) -> TrackedAgent:
    agent = TrackedAgent(id="a1", model=model)
    agent.automata_config_id = uuid.uuid4()
    agent.automata_model_id = model.id
    return agent


async def test_run_com_sucesso_registra_status_e_duracao(records: list[RunRecord]) -> None:
    agent = _agent(ReplayModel(id="claude-haiku-4-5"))
    output = await agent.arun("oi", user_id="u1")

    assert len(records) == 1
    record = records[0]
    assert record.status == "success"
    assert record.run_id == output.run_id
    assert record.user_id == "u1"
    assert record.duration_ms >= 0
    assert record.model_id == "claude-haiku-4-5"


async def test_run_com_erro_registra_erro(records: list[RunRecord]) -> None:
    agent = _agent(FailingModel(id="x"))
    await agent.arun("oi")

    assert [r.status for r in records] == ["error"]
    assert records[0].error is not None
    assert "fora do ar" in records[0].error


async def test_stream_com_sucesso(records: list[RunRecord]) -> None:
    agent = _agent(ReplayModel(id="claude-haiku-4-5"))
    events = [e async for e in agent.arun("oi", stream=True, stream_events=True)]

    assert events
    assert [r.status for r in records] == ["success"]
    assert records[0].run_id is not None


async def test_stream_com_erro(records: list[RunRecord]) -> None:
    agent = _agent(FailingModel(id="x"))
    _ = [e async for e in agent.arun("oi", stream=True, stream_events=True)]

    assert [r.status for r in records] == ["error"]


async def test_agente_sem_config_nao_registra(records: list[RunRecord]) -> None:
    agent = TrackedAgent(id="a1", model=ReplayModel(id="x"))
    await agent.arun("oi")
    assert records == []


def test_status_por_evento_quando_nao_ha_saida() -> None:
    assert tracking._status_of(None, "RunError") == "error"
    assert tracking._status_of(None, "RunCancelled") == "cancelled"
    assert tracking._status_of(None, "RunPaused") == "paused"
    assert tracking._status_of(None, "RunCompleted") == "success"
