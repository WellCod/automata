"""Testes do ReplayModel e do resolve_model com DEMO_REPLAY=true."""

from collections.abc import Generator

import pytest

from app.agents import replay as replay_module
from app.agents.replay import ReplayModel, _load_fixture, _next_response


@pytest.fixture(autouse=True)
def reset_counters() -> Generator[None, None, None]:
    """Limpa o cache de contadores entre testes para evitar dependência de ordem."""
    replay_module._COUNTERS.clear()
    yield
    replay_module._COUNTERS.clear()


# --- _load_fixture ---


def test_load_fixture_modelo_existente() -> None:
    respostas = _load_fixture("claude-sonnet-4-6")
    assert isinstance(respostas, list)
    assert len(respostas) > 0
    assert all(isinstance(r, str) for r in respostas)


def test_load_fixture_modelo_inexistente_usa_default() -> None:
    respostas = _load_fixture("modelo-inexistente-xyz")
    default = _load_fixture("default")
    assert respostas == default


# --- _next_response ---


def test_next_response_retorna_string() -> None:
    resp = _next_response("claude-haiku-4-5")
    assert isinstance(resp, str)
    assert len(resp) > 0


def test_next_response_cicla() -> None:
    fixture = _load_fixture("claude-sonnet-4-6")
    n = len(fixture)
    respostas = [_next_response("claude-sonnet-4-6") for _ in range(n + 1)]
    assert respostas[n] == respostas[0]


def test_next_response_modelo_fallback() -> None:
    resp = _next_response("modelo-sem-fixture")
    assert isinstance(resp, str)


# --- ReplayModel.invoke ---


def test_invoke_retorna_model_response() -> None:
    from agno.models.response import ModelResponse

    model = ReplayModel(id="claude-sonnet-4-6")
    result = model.invoke()
    assert isinstance(result, ModelResponse)
    assert result.role == "assistant"
    assert isinstance(result.content, str)
    assert len(result.content) > 0  # type: ignore[arg-type]


def test_invoke_usa_model_id_correto() -> None:
    model_haiku = ReplayModel(id="claude-haiku-4-5")
    model_sonnet = ReplayModel(id="claude-sonnet-4-6")
    resp_haiku = model_haiku.invoke().content
    resp_sonnet = model_sonnet.invoke().content
    # fixture files são diferentes — conteúdos não precisam ser iguais
    assert isinstance(resp_haiku, str)
    assert isinstance(resp_sonnet, str)


# --- ReplayModel.ainvoke ---


async def test_ainvoke_retorna_model_response() -> None:
    from agno.models.response import ModelResponse

    model = ReplayModel(id="claude-opus-4-7")
    result = await model.ainvoke()
    assert isinstance(result, ModelResponse)
    assert result.role == "assistant"


# --- ReplayModel.invoke_stream ---


def test_invoke_stream_retorna_iterator() -> None:
    from agno.models.response import ModelResponse

    model = ReplayModel(id="claude-sonnet-4-6")
    items = list(model.invoke_stream())
    assert len(items) == 1
    assert isinstance(items[0], ModelResponse)
    assert items[0].role == "assistant"


# --- ReplayModel.ainvoke_stream ---


async def test_ainvoke_stream_retorna_async_iterator() -> None:
    from agno.models.response import ModelResponse

    model = ReplayModel(id="claude-haiku-4-5")
    items = [item async for item in model.ainvoke_stream()]
    assert len(items) == 1
    assert isinstance(items[0], ModelResponse)


# --- métodos não implementados ---


def test_parse_provider_response_nao_implementado() -> None:
    model = ReplayModel(id="replay")
    with pytest.raises(NotImplementedError):
        model._parse_provider_response(None)


def test_parse_provider_response_delta_nao_implementado() -> None:
    model = ReplayModel(id="replay")
    with pytest.raises(NotImplementedError):
        model._parse_provider_response_delta(None)


# --- atributos do dataclass ---


def test_replay_model_atributos_padrao() -> None:
    model = ReplayModel(id="meu-modelo")
    assert model.id == "meu-modelo"
    assert model.name == "Replay"
    assert model.provider == "Demo"


# --- resolve_model com DEMO_REPLAY ---


def test_resolve_model_demo_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_REPLAY", "true")
    from app.agents.models_map import resolve_model

    model = resolve_model("claude-sonnet-4-6")
    assert isinstance(model, ReplayModel)
    assert model.id == "claude-sonnet-4-6"


def test_resolve_model_demo_replay_flag_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_REPLAY", "1")
    from app.agents.models_map import resolve_model

    model = resolve_model("claude-haiku-4-5")
    assert isinstance(model, ReplayModel)
