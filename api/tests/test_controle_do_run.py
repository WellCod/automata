"""Controle do run (ADR-0027): seção `run` do payload e o que ela liga no agente e no time."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.config import ConfigPayload
from app.settings import get_settings


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "x")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "x")
    monkeypatch.setenv("DEMO_REPLAY", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _payload(**run: object) -> ConfigPayload:
    return ConfigPayload.model_validate({"model_id": "claude-sonnet-4-6", "run": run})


def test_padrao_vazio_nao_muda_versao_antiga() -> None:
    old = ConfigPayload.model_validate({"model_id": "gpt-4o"})
    assert old.run.tool_call_limit is None


@pytest.mark.parametrize("limit", [0, 101])
def test_limite_fora_da_faixa_e_recusado(limit: int) -> None:
    with pytest.raises(ValidationError):
        _payload(tool_call_limit=limit)


def test_agente_e_lider_do_time_recebem_o_limite() -> None:
    from app.agents.factory import ResolvedTeam, ResolvedVersion, agent_from, team_from

    agent = agent_from(
        uuid4(), ResolvedVersion("a", "Use para a", _payload(tool_call_limit=3)), tracked=False
    )
    assert agent.tool_call_limit == 3
    unlimited = agent_from(uuid4(), ResolvedVersion("b", "Use para b", _payload()), tracked=False)
    assert unlimited.tool_call_limit is None

    member_id = uuid4()
    leader = ConfigPayload.model_validate(
        {
            "model_id": "claude-sonnet-4-6",
            "run": {"tool_call_limit": 5},
            "team": {"members": [{"agent_id": str(member_id)}]},
        }
    )
    team = team_from(
        uuid4(),
        ResolvedTeam(
            leader=ResolvedVersion("t", "Use para t", leader),
            members=[(member_id, ResolvedVersion("m", "Use para m", _payload(tool_call_limit=2)))],
        ),
    )
    assert team.tool_call_limit == 5
    assert team.members[0].tool_call_limit == 2  # type: ignore[union-attr]
