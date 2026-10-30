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


def test_reserva_precisa_ser_da_matriz_diferente_e_com_as_capabilities() -> None:
    from app.services.config import ConfigService

    def errors(**data: object) -> list[str]:
        return ConfigService._fallback_errors(ConfigPayload.model_validate(data))

    ok = {"model_id": "claude-sonnet-4-6", "run": {"fallback_models": ["gpt-4o"]}}
    assert errors(**ok) == []
    assert (
        "próprio modelo principal"
        in errors(model_id="gpt-4o", run={"fallback_models": ["gpt-4o"]})[0]
    )
    assert (
        "não suportado"
        in errors(model_id="gpt-4o", run={"fallback_models": ["modelo-inventado"]})[0]
    )
    # o3 não tem visão: um agente com visão não pode cair nele
    sem_visao = errors(
        model_id="gpt-4o", capabilities={"vision": True}, run={"fallback_models": ["o3"]}
    )
    assert sem_visao == ["modelo reserva: 'o3' não suporta vision"]
    with pytest.raises(ValidationError):
        _payload(fallback_models=["gpt-4o", "gpt-4o"])


def test_retry_do_provedor_e_reservas_no_modelo(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.agents.factory import fallback_for, model_for

    monkeypatch.setenv("DEMO_REPLAY", "false")
    get_settings.cache_clear()
    payload = _payload(provider_retries=2, fallback_models=["gpt-4o", "gpt-4o-mini"])
    model = model_for("claude-sonnet-4-6", payload)
    assert (model.retries, model.delay_between_retries, model.exponential_backoff) == (2, 1, True)
    config = fallback_for(payload)
    assert config is not None
    assert [m.id for m in config.on_error] == ["gpt-4o", "gpt-4o-mini"]  # type: ignore[union-attr]
    assert [m.id for m in config.on_rate_limit] == ["gpt-4o", "gpt-4o-mini"]  # type: ignore[union-attr]
    # a reserva também repete a chamada antes de passar à próxima
    assert all(m.retries == 2 for m in config.on_error)  # type: ignore[union-attr]
    assert fallback_for(_payload()) is None


def test_demo_sem_retry_nem_reserva() -> None:
    from app.agents.factory import fallback_for, model_for

    payload = _payload(provider_retries=2, fallback_models=["gpt-4o"])
    assert model_for("claude-sonnet-4-6", payload).retries == 0
    assert fallback_for(payload) is None


def test_custo_segue_o_modelo_que_respondeu() -> None:
    from agno.metrics import ModelMetrics, RunMetrics

    from app.pricing import answered_by, estimate_cost, run_cost

    # o principal gastou a entrada e falhou; a reserva respondeu
    metrics = RunMetrics(
        input_tokens=3_000,
        output_tokens=500,
        details={
            "model": [
                ModelMetrics(id="claude-sonnet-4-6", input_tokens=1_000, output_tokens=0),
                ModelMetrics(id="gpt-4o", input_tokens=2_000, output_tokens=500),
            ]
        },
    )
    expected = (estimate_cost("claude-sonnet-4-6", 1_000, 0) or 0) + (
        estimate_cost("gpt-4o", 2_000, 500) or 0
    )
    assert run_cost(metrics, "claude-sonnet-4-6") == pytest.approx(expected)
    assert answered_by(metrics, "claude-sonnet-4-6") == "gpt-4o"

    # sem detalhe por modelo, vale o total no modelo configurado, como antes
    plain = RunMetrics(input_tokens=1_000, output_tokens=100)
    assert run_cost(plain, "gpt-4o") == estimate_cost("gpt-4o", 1_000, 100)
    assert answered_by(plain, "gpt-4o") == "gpt-4o"
    # custo informado pelo provedor vale sobre a tabela
    assert run_cost(RunMetrics(cost=0.5), "gpt-4o") == 0.5
    assert run_cost(None, "gpt-4o") is None
