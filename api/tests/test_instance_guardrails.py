"""Piso de guardrails da instância (ADR-0034): o agente só endurece."""

import os
from collections.abc import Generator
from typing import Any
from uuid import UUID

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.guardrails.instance import effective
from app.schemas.config import GuardrailSettings
from app.settings import get_settings

CPF = "529.982.247-25"


def _g(**data: Any) -> GuardrailSettings:
    return GuardrailSettings.model_validate(data)


# --- combinação (sem banco) ---


def test_sem_piso_vale_o_do_agente() -> None:
    own = _g(prompt_injection=True)
    assert effective(None, own) is own


def test_modo_mais_forte_e_tipos_so_dos_lados_ligados() -> None:
    base = _g(pii={"mode": "mask", "types": ["cpf"]})
    off = effective(base, _g())
    # o padrão do agente é "todos os tipos", mas desligado não conta
    assert (off.pii.mode, off.pii.types) == ("mask", ["cpf"])
    block = effective(base, _g(pii={"mode": "block", "types": ["email"]}))
    assert (block.pii.mode, block.pii.types) == ("block", ["cpf", "email"])
    weaker = effective(_g(pii={"mode": "block", "types": ["cpf"]}), _g(pii={"mode": "mask"}))
    assert weaker.pii.mode == "block"


def test_padroes_proprios_somam_e_o_rotulo_da_instancia_vence() -> None:
    mat = {"label": "matrícula", "prefix": "MAT", "min_digits": 6, "max_digits": 8}
    base = _g(pii={"mode": "mask", "types": [], "custom": [mat]})
    own = _g(
        pii={
            "mode": "mask",
            "types": [],
            "custom": [
                {**mat, "label": "Matrícula", "prefix": "M"},
                {"label": "contrato", "prefix": "CT", "min_digits": 8, "max_digits": 10},
            ],
        }
    )
    custom = effective(base, own).pii.custom
    assert [(p.label, p.prefix) for p in custom] == [("matrícula", "MAT"), ("contrato", "CT")]


def test_listas_somam_limite_menor_e_ligado_se_um_ligar() -> None:
    base = _g(
        prompt_injection=True,
        blocked_topics=["política"],
        max_input_chars=2000,
        output={"pii": True, "pii_types": ["cpf"], "blocked_terms": ["concorrente"]},
    )
    own = _g(blocked_topics=["religião"], max_input_chars=5000, output={"blocked_terms": ["x-y-z"]})
    eff = effective(base, own)
    assert eff.prompt_injection is True
    assert eff.blocked_topics == ["política", "religião"]
    assert eff.max_input_chars == 2000
    assert eff.output.pii is True and eff.output.pii_types == ["cpf"]
    assert eff.output.blocked_terms == ["concorrente", "x-y-z"]
    assert effective(_g(), _g(max_input_chars=300)).max_input_chars == 300


def test_classificador_combina_checagens_e_a_falha_mais_dura() -> None:
    base = _g(
        classifier={"model_id": "gpt-4o-mini", "checks": ["injection"], "on_failure": "block"}
    )
    own = _g(
        classifier={
            "model_id": "claude-haiku-4-5",
            "checks": ["off_topic"],
            "scope": "pedidos da loja",
            "on_failure": "allow",
        }
    )
    eff = effective(base, own).classifier
    assert eff is not None
    # o modelo é o do piso (Fase 43); o escopo do agente vale porque o piso não tem um
    assert (eff.model_id, eff.checks, eff.scope, eff.on_failure) == (
        "gpt-4o-mini",
        ["off_topic", "injection"],
        "pedidos da loja",
        "block",
    )
    only_floor = effective(base, _g()).classifier
    assert only_floor is not None and only_floor.model_id == "gpt-4o-mini"


def test_mensagem_de_bloqueio_e_do_agente() -> None:
    eff = effective(_g(blocked_message="piso"), _g(blocked_message="do agente"))
    assert eff.blocked_message == "do agente"


# --- API e run (com banco) ---


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        os.environ["DATABASE_URL"] = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        # depois do DATABASE_URL: importar o app conecta no banco
        import app.agents.factory as factory
        from app.main import create_app

        patch = pytest.MonkeyPatch()
        patch.setenv("DEMO_REPLAY", "true")
        get_settings.cache_clear()
        model = ReplayModel(id="claude-haiku-4-5")
        patch.setattr(factory, "resolve_model", lambda *a, **k: model)
        app = create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        with TestClient(app) as c:
            yield c
        patch.undo()
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _agent(client: TestClient, guardrails: dict[str, Any]) -> str:
    created = client.post("/api/v1/configs", json={"name": "piso", "description": "x"})
    agent_id = str(created.json()["id"])
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "piso",
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5", "guardrails": guardrails},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    return agent_id


def test_piso_vale_no_proximo_run_sem_publicar(client: TestClient) -> None:
    from app.agents.factory import load_version
    from app.guardrails.instance import forget

    agent_id = _agent(client, {})
    floor = {"settings": {"pii": {"mode": "block", "types": ["cpf"]}}}
    assert client.put("/api/v1/instance-guardrails", json=floor).status_code == 200
    forget()
    assert load_version(UUID(agent_id), None).payload.guardrails.pii.mode == "block"

    eff = client.get(f"/api/v1/configs/{agent_id}/guardrails/effective").json()
    assert eff["own"]["pii"]["mode"] == "off"
    assert eff["floor"]["pii"]["mode"] == "block"
    assert eff["effective"]["pii"]["types"] == ["cpf"]
    # sem rascunho, o pedido pelo rascunho responde pela vigente, sem 404 (Fase 43)
    as_draft = client.get(f"/api/v1/configs/{agent_id}/guardrails/effective?draft=true")
    assert as_draft.status_code == 200 and as_draft.json()["floor"] == eff["floor"]

    resp = client.post(
        f"/agents/{agent_id}/runs", data={"message": f"meu cpf é {CPF}", "stream": "false"}
    )
    assert resp.status_code == 200, resp.text
    assert CPF not in resp.text
    runs = client.get(f"/api/v1/configs/{agent_id}/runs").json()
    assert runs["items"][0]["status"] == "blocked"

    assert client.put("/api/v1/instance-guardrails", json={"settings": None}).json() == {
        "settings": None,
        "updated_by": None,
        "updated_at": None,
    }
    forget()
    assert load_version(UUID(agent_id), None).payload.guardrails.pii.mode == "off"


def test_piso_validado_como_o_agente(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.services.config as service

    # sem chave da OpenAI e fora do modo demo, a moderação falharia em todo run
    monkeypatch.setattr(service, "demo_replay", lambda: False)
    monkeypatch.setattr(service, "moderation_available", lambda: False)
    bad = client.put("/api/v1/instance-guardrails", json={"settings": {"moderation": True}})
    assert bad.status_code == 422
    model = {"settings": {"classifier": {"model_id": "inventado", "checks": ["injection"]}}}
    assert client.put("/api/v1/instance-guardrails", json=model).status_code == 422


def test_classificador_da_saida_no_run_de_verdade(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O post hook assíncrono roda no arun do AgentOS e marca o run como bloqueado."""
    import app.agents.models_map as models_map
    from tests.fake_models import FixedReplyModel

    verdict = '{"verdict": "block", "category": "prompt_leak", "reason": "vaza"}'
    monkeypatch.setattr(models_map, "demo_replay", lambda: False)
    monkeypatch.setattr(
        models_map,
        "resolve_model",
        lambda model_id, *a, **k: FixedReplyModel(id=model_id, reply=verdict, tokens=5),
    )
    classifier = {"model_id": "claude-haiku-4-5", "checks": ["prompt_leak"]}
    agent_id = _agent(
        client, {"output": {"classifier": classifier}, "blocked_message": "Não posso."}
    )
    resp = client.post(f"/agents/{agent_id}/runs", data={"message": "oi", "stream": "false"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["content"] == "Não posso."
    [run] = client.get(f"/api/v1/configs/{agent_id}/runs").json()["items"]
    assert (run["status"], run["blocked_by"]) == ("blocked", "output_classifier")


def test_agente_nao_troca_o_modelo_nem_o_escopo_do_piso() -> None:
    """Fase 43: modelo sem chave com falha aberta, ou outro escopo, anulavam o piso."""
    base = _g(
        classifier={
            "model_id": "gpt-4o-mini",
            "checks": ["off_topic"],
            "scope": "pedidos da loja",
            "on_failure": "allow",
        }
    )
    own = _g(
        classifier={
            "model_id": "claude-haiku-4-5",
            "checks": ["injection"],
            "scope": "qualquer assunto",
            "on_failure": "allow",
        }
    )
    eff = effective(base, own).classifier
    assert eff is not None
    assert (eff.model_id, eff.scope) == ("gpt-4o-mini", "pedidos da loja")
