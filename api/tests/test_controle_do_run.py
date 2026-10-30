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


PEDIDO = {
    "type": "object",
    "properties": {
        "categoria": {"enum": ["troca", "reembolso", "duvida"]},
        "valor": {"type": "number"},
    },
    "required": ["categoria"],
    "additionalProperties": False,
}


def test_schema_valido_na_escrita() -> None:
    from app.agents.output_schema import schema_problems

    assert schema_problems(PEDIDO) == []
    assert "type object" in schema_problems({"type": "array", "items": {"type": "string"}})[0]
    assert "inválido" in schema_problems({"type": "object", "properties": {"x": {"type": 3}}})[0]
    big = {"type": "object", "description": "x" * 40_000}
    assert "maior que 32 KB" in schema_problems(big)[0]


def test_schema_exige_capability_e_nao_vale_em_workflow() -> None:
    from types import SimpleNamespace

    from app.schemas.config import ConfigKind
    from app.services.config import ConfigService

    def errors(kind: ConfigKind, **data: object) -> list[str]:
        config: object = SimpleNamespace(kind=kind)
        payload = ConfigPayload.model_validate(data)
        return ConfigService._schema_errors(config, payload)  # type: ignore[arg-type]

    sem_flag = errors(ConfigKind.agent, model_id="gpt-4o", output_schema=PEDIDO)
    assert sem_flag == ["schema de saída exige a capability structured_output ligada"]
    ok = errors(
        ConfigKind.agent,
        model_id="gpt-4o",
        capabilities={"structured_output": True},
        output_schema=PEDIDO,
    )
    assert ok == []
    assert errors(ConfigKind.workflow, output_schema=PEDIDO) == [
        "workflow não tem saída estruturada própria"
    ]


@pytest.mark.parametrize(
    ("content", "passed"),
    [
        ({"categoria": "troca", "valor": 120.5}, True),
        ('{"categoria": "duvida"}', True),
        ({"categoria": "outra"}, False),
        ({"valor": 10}, False),
        ({"categoria": "troca", "extra": 1}, False),
        ("Claro! A categoria é troca.", False),
    ],
)
def test_resposta_conferida_contra_o_schema(content: object, passed: bool) -> None:
    from app.agents.output_schema import schema_verdict

    verdict = schema_verdict(PEDIDO, content)
    assert verdict["passed"] is passed
    assert bool(verdict["errors"]) is not passed


def test_agente_recebe_o_schema() -> None:
    from app.agents.factory import ResolvedVersion, agent_from

    payload = ConfigPayload.model_validate(
        {
            "model_id": "gpt-4o",
            "capabilities": {"structured_output": True},
            "output_schema": PEDIDO,
        }
    )
    agent = agent_from(uuid4(), ResolvedVersion("a", "Use para a", payload), tracked=False)
    assert agent.output_schema == PEDIDO


async def test_checagem_schema_na_suite(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from app.evals import runner

    reply: dict[str, object] = {"categoria": "reembolso"}
    schema: dict[str, object] | None = PEDIDO

    def agent_from(config_id: object, resolved: object, *, tracked: bool) -> object:
        return SimpleNamespace(output_schema=schema, arun=None)

    monkeypatch.setattr(runner, "load_version", lambda config_id, version_id: None)
    monkeypatch.setattr(runner, "agent_from", agent_from)
    snapshot = {
        "id": str(uuid4()),
        "name": "c",
        "input": "quero trocar",
        "checks": [{"type": "schema"}],
    }

    planned = runner.plan_case(0, snapshot, uuid4(), "agent", uuid4(), None)
    assert planned.agno_case is not None
    scorer = planned.agno_case.scorer
    assert scorer is not None
    assert (await scorer.ascore(SimpleNamespace(content=reply))).passed is True
    bad = await scorer.ascore(SimpleNamespace(content={"categoria": "outra"}))
    assert bad.passed is False and "fora do schema" in (bad.reason or "")

    # versão sem schema: a checagem não roda e o motivo fica no resultado
    schema = None
    skipped = runner.plan_case(0, snapshot, uuid4(), "agent", uuid4(), None)
    assert skipped.agno_case is None
    assert skipped.skipped == {"schema": runner.NO_SCHEMA}
    result = runner.result_from(skipped, None)
    assert result.status == "not_evaluated"
    assert result.checks == [
        {"type": "schema", "passed": None, "errors": [], "reason": runner.NO_SCHEMA}
    ]


def test_guardrail_de_saida_olha_dentro_do_json() -> None:
    from agno.exceptions import OutputCheckError
    from agno.run.agent import RunOutput

    from app.guardrails.output import output_guardrail
    from app.schemas.config import GuardrailSettings, OutputRule

    hook = output_guardrail(
        GuardrailSettings(output=OutputRule(pii=True), blocked_message="Resposta retida.")
    )
    assert hook is not None
    out = RunOutput(content={"categoria": "troca", "cpf": "529.982.247-25"})
    with pytest.raises(OutputCheckError):
        hook(run_output=out)
    assert out.content == "Resposta retida."
    limpo = RunOutput(content={"categoria": "troca"})
    hook(run_output=limpo)
    assert limpo.content == {"categoria": "troca"}
