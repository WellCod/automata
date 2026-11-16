"""Prazo e novas tentativas nos clientes de provedor (Fase 51, OPS-03).

Os SDKs esperam 600 s com duas novas tentativas: provedor que aceita a conexão e não
responde segurava cada run por até meia hora, sem erro na tela.
"""

import pytest

from app.agents.models_map import PROVIDER_TIMEOUT_SECONDS, resolve_model
from app.schemas.config import CapabilityFlags


@pytest.fixture(autouse=True)
def _sem_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_REPLAY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-teste")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-teste")


@pytest.mark.parametrize("model_id", ["claude-haiku-4-5", "gpt-4o"])
def test_modelo_com_prazo_e_uma_nova_tentativa(model_id: str) -> None:
    model = resolve_model(model_id)
    client = model.get_client()  # type: ignore[attr-defined]
    assert client.timeout == PROVIDER_TIMEOUT_SECONDS
    assert client.max_retries == 1


def test_extended_thinking_mantem_o_prazo() -> None:
    model = resolve_model("claude-sonnet-4-6", CapabilityFlags(extended_thinking=True))
    client = model.get_client()  # type: ignore[attr-defined]
    assert client.timeout == PROVIDER_TIMEOUT_SECONDS
    assert client.max_retries == 1


def test_embedders_com_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.knowledge.embedders import EMBEDDER_TIMEOUT_SECONDS, build_embedder

    openai = build_embedder("openai", "text-embedding-3-small", 1536)
    assert openai.client.timeout == EMBEDDER_TIMEOUT_SECONDS  # type: ignore[attr-defined]
    voyage = build_embedder("voyage", "voyage-3.5", 1024)
    assert voyage.timeout == EMBEDDER_TIMEOUT_SECONDS  # type: ignore[attr-defined]


def test_s3_com_prazo_explicito() -> None:
    from app.knowledge.sources import S3Source
    from app.schemas.knowledge_connector import S3Settings

    source = S3Source(S3Settings(bucket="docs", region="us-east-1"), {"access_key_id": "k"})
    config = source._client().meta.config
    assert (config.connect_timeout, config.read_timeout) == (10, 60)
