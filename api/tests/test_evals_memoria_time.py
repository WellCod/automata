"""Evals da memória em time e do resumo com modelo próprio (ADR-0035).

Sem banco e sem rede. Errar o dono da memória é mostrar ao time o que um agente
guardou, ou ao agente o que o time guardou; errar o resumo é cobrar o resumo no
preço do modelo grande ou perder o retry da versão.
"""

from typing import Any

import pytest
from agno.db.postgres import PostgresDb
from agno.db.schemas.memory import UserMemory

from app.agents import memory
from app.agents.memory import AgentMemoryManager, memory_kwargs, owner_of
from app.guardrails.pii import CustomPattern
from app.schemas.config import MemorySettings


class FakeDb:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_user_memories(self, **kwargs: Any) -> list[UserMemory]:
        self.calls.append(kwargs)
        return [UserMemory(memory="veste M", memory_id="1", user_id="ana", team_id="time")]


@pytest.mark.parametrize(
    ("row", "owner"),
    [
        (UserMemory(memory="x", agent_id="agente"), "agente"),
        (UserMemory(memory="x", team_id="time"), "time"),
        # o Agno grava um ou outro; com os dois, o agente é quem guardou
        (UserMemory(memory="x", agent_id="agente", team_id="time"), "agente"),
        (UserMemory(memory="x"), None),
    ],
)
def test_dono_da_memoria(row: UserMemory, owner: str | None) -> None:
    assert owner_of(row) == owner


def test_time_le_pelo_team_id_e_nunca_pelo_agent_id() -> None:
    db = FakeDb()
    manager = AgentMemoryManager(agent_id="time", team=True, db=db)  # type: ignore[arg-type]
    found = manager.read_from_db(user_id="ana")
    assert db.calls == [{"user_id": "ana", "team_id": "time"}]
    assert found is not None and [m.memory for m in found["ana"]] == ["veste M"]
    agent = AgentMemoryManager(agent_id="agente", db=db)  # type: ignore[arg-type]
    agent.read_from_db(user_id="ana")
    assert db.calls[-1] == {"user_id": "ana", "agent_id": "agente"}


def test_memoria_do_time_so_com_usuario(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory, "memory_db", lambda: FakeDb())
    assert memory_kwargs("time", MemorySettings(enabled=True), None, team=True) == {}
    kwargs = memory_kwargs("time", MemorySettings(enabled=True), "ana", team=True)
    assert kwargs["memory_manager"].team is True and kwargs["update_memory_on_run"] is True


def test_mascara_do_time_usa_os_padroes_do_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PostgresDb, "upsert_user_memory", lambda self, m, *a, **k: m)
    monkeypatch.setattr(memory, "memory_db", lambda: FakeDb())
    monkeypatch.setattr(memory, "_custom_by_agent", {})
    mat = CustomPattern("matrícula", "MAT", 6, 8)
    memory_kwargs("time", MemorySettings(enabled=True), "ana", (mat,), team=True)
    db = memory.MaskingDb.__new__(memory.MaskingDb)
    saved = db.upsert_user_memory(UserMemory(memory="matrícula MAT 1234567", team_id="time"))
    assert "1234567" not in saved.memory
    other = db.upsert_user_memory(UserMemory(memory="matrícula MAT 1234567", agent_id="outro"))
    assert other.memory == "matrícula MAT 1234567"


def test_resumo_com_modelo_proprio_herda_o_retry_da_versao(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.agents.factory as factory
    from app.agents.factory import compaction_for
    from app.schemas.config import ConfigPayload

    monkeypatch.setattr(factory, "demo_replay", lambda: False)
    payload = ConfigPayload.model_validate(
        {
            "model_id": "claude-sonnet-4-6",
            "run": {"provider_retries": 2},
            "conversation": {"compaction": True, "summary_model": "claude-haiku-4-5"},
        }
    )
    compaction = compaction_for(payload)
    assert compaction is not None and compaction.model is not None
    model: Any = compaction.model
    assert model.id == "claude-haiku-4-5" and model.retries == 2
