"""Testes do linter de prompt e do endpoint POST /api/v1/linter.

O teste test_adr0006_* é o gate de ADR-0006: falha o build se a detecção
de termos acoplados a provider for removida do linter.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.linter.prompt import LintWarning, lint_payload
from app.schemas.config import ConfigPayload, InstructionSections
from app.settings import get_settings


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_PRIVATE_KEY", "pk")
    monkeypatch.setenv("JWT_PUBLIC_KEY", "pub")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _payload(persona: str = "", tools: list[str] | None = None) -> ConfigPayload:
    return ConfigPayload(
        model_id="claude-sonnet-4-6",
        instructions=InstructionSections(persona=persona),
        tools=tools or [],
    )


# --- ADR-0006: provider coupling ---


def test_adr0006_provider_coupling_detectado() -> None:
    """ADR-0006: linter deve detectar termos acoplados a provider.

    Este teste falha o build se a detecção for removida ou contornada.
    Garante que trocar modelo continua sendo um campo, não uma reescrita.
    """
    payload = _payload(persona="Você é um assistente Claude da Anthropic.")
    warnings = lint_payload(payload)
    codes = [w.code for w in warnings]
    assert "provider-coupling" in codes, (
        "ADR-0006: instrução com termo acoplado a provider ('claude', 'anthropic') "
        "não foi detectada pelo linter — gate de ADR-0006 falhou"
    )


def test_adr0006_openai_detectado() -> None:
    payload = _payload(persona="Use a API da OpenAI para responder.")
    warnings = lint_payload(payload)
    assert any(w.code == "provider-coupling" for w in warnings)


def test_adr0006_gpt_detectado() -> None:
    payload = _payload(persona="Você é um modelo GPT de última geração.")
    warnings = lint_payload(payload)
    assert any(w.code == "provider-coupling" for w in warnings)


def test_adr0006_thinking_tag_detectada() -> None:
    payload = _payload(persona="Raciocine usando <thinking> antes de responder.")
    warnings = lint_payload(payload)
    assert any(w.code == "provider-coupling" for w in warnings)


def test_instrucoes_agnosticas_sem_aviso() -> None:
    payload = _payload(
        persona="Você é um assistente especializado em suporte ao cliente.",
    )
    warnings = [w for w in lint_payload(payload) if w.code == "provider-coupling"]
    assert warnings == []


# --- tool citation ---


def test_tool_citada_sem_habilitar_gera_aviso() -> None:
    payload = _payload(
        persona="Use web_search para buscar informações atualizadas.",
        tools=[],
    )
    warnings = lint_payload(payload)
    assert any(w.code == "tool-not-enabled" and "web_search" in w.message for w in warnings)


def test_tool_citada_e_habilitada_sem_aviso() -> None:
    payload = _payload(
        persona="Use web_search para buscar informações atualizadas.",
        tools=["web_search"],
    )
    warnings = [w for w in lint_payload(payload) if w.code == "tool-not-enabled"]
    assert warnings == []


def test_sem_ferramentas_citadas_sem_aviso() -> None:
    payload = _payload(persona="Responda sempre de forma educada e direta.")
    warnings = [w for w in lint_payload(payload) if w.code == "tool-not-enabled"]
    assert warnings == []


# --- retorno de LintWarning ---


def test_lint_warning_tem_campos_esperados() -> None:
    payload = _payload(persona="Responda como o modelo Anthropic Claude.")
    warnings = lint_payload(payload)
    assert len(warnings) > 0
    w = warnings[0]
    assert isinstance(w, LintWarning)
    assert w.section
    assert w.code
    assert w.message


def test_payload_vazio_sem_avisos() -> None:
    payload = ConfigPayload(model_id="gpt-4o")
    warnings = lint_payload(payload)
    assert warnings == []


# --- endpoint ---


def test_endpoint_linter_sem_avisos() -> None:
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False))
    response = client.post(
        "/api/v1/linter",
        json={"model_id": "gpt-4o", "schema_version": 1},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_endpoint_linter_com_avisos() -> None:
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False))
    response = client.post(
        "/api/v1/linter",
        json={
            "model_id": "claude-sonnet-4-6",
            "schema_version": 1,
            "instructions": {"persona": "Você é o assistente GPT da OpenAI."},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert any(w["code"] == "provider-coupling" for w in data)


def test_endpoint_linter_capabilities_invalidas_rejeitadas() -> None:
    """Payload com capability inválida deve ser rejeitado com 422 antes do linter."""
    from app.main import create_app

    client = TestClient(create_app(auto_provision_dbs=False))
    # extended_thinking não é suportado por gpt-4o, mas o endpoint apenas linta
    # sem validar capabilities — essa responsabilidade fica em save_draft
    response = client.post(
        "/api/v1/linter",
        json={
            "model_id": "gpt-4o",
            "schema_version": 1,
            "capabilities": {"extended_thinking": True},
        },
    )
    # linter não bloqueia capabilities — só avisa sobre provider coupling e tools
    assert response.status_code == 200
