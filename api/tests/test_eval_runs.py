"""Execução da suíte com o runner do Agno, resultado por caso e runs fora das conversas."""

import os
import uuid
from collections.abc import Generator
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.evals.runner import TextScorer
from app.schemas.eval import TextCheck
from app.settings import get_settings
from tests.fake_models import CountingModel, FixedReplyModel

REPLY = "Prazo de troca: 30 dias corridos a partir do recebimento."


JUDGE = "gpt-4o-mini"
VERDICT = '{"passed": true, "reason": "Cita o prazo de 30 dias."}'


def _model(model_id: str, *_: Any, **__: Any) -> ReplayModel:
    # o juiz responde no schema binário do AgentAsJudgeEval
    if model_id == JUDGE:
        return FixedReplyModel(id=model_id, reply=VERDICT, tokens=7)
    # versão "piorada" para os testes de regressão: troca o modelo e perde o prazo
    if model_id == "claude-sonnet-4-6":
        return FixedReplyModel(id=model_id, reply="Não sei informar.", tokens=10)
    # responde quantas mensagens do usuário recebeu: mostra se o contexto chegou
    if model_id == "gpt-4o":
        return CountingModel(id=model_id)
    return FixedReplyModel(id=model_id, reply=REPLY, tokens=10)


async def test_scorer_de_texto() -> None:
    class Run:
        content = REPLY

    scorer = TextScorer(
        [TextCheck(kind="contains", value="30 DIAS"), TextCheck(kind="not_contains", value="prazo")]
    )
    score = await scorer.ascore(Run())
    assert (score.passed, score.value) == (False, 0.5)
    assert score.reason == "falhou: not_contains 'prazo'"
    assert [c["passed"] for c in (score.detail or {})["checks"]] == [True, False]


@pytest.fixture(scope="module")
def client() -> Generator[TestClient, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        import app.agents.factory as factory
        import app.agents.models_map as models_map

        original = factory.resolve_model, models_map.resolve_model
        factory.resolve_model = _model  # type: ignore[assignment]
        models_map.resolve_model = _model  # type: ignore[assignment]
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        factory.resolve_model, models_map.resolve_model = original  # type: ignore[assignment]
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _agent(client: TestClient, name: str, publish: bool = True) -> str:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = str(client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"])
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={**body, "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    if publish:
        client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return config_id


def _case(client: TestClient, config_id: str, name: str, checks: list[dict[str, Any]]) -> None:
    client.post(
        f"/api/v1/configs/{config_id}/eval-cases",
        json={"name": name, "input": "Qual o prazo para trocar?", "checks": checks},
    ).raise_for_status()


def _start(client: TestClient, config_id: str, **body: Any) -> Any:
    return client.post(f"/api/v1/configs/{config_id}/eval-runs", json=body)


def test_suite_roda_cada_caso_e_marca_os_runs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # no modo demo o juiz não roda: o caso só com juiz fica não avaliado
    monkeypatch.setenv("DEMO_REPLAY", "true")
    agent = _agent(client, "atendimento")
    _case(client, agent, "prazo", [{"type": "text", "kind": "contains", "value": "30 dias"}])
    _case(client, agent, "sem prazo", [{"type": "text", "kind": "not_contains", "value": "prazo"}])
    _case(client, agent, "busca na base", [{"type": "tools", "tools": ["buscar_politicas"]}])
    _case(client, agent, "só juiz", [{"type": "judge", "criteria": "Cita o prazo de 30 dias"}])

    started = _start(client, agent)
    assert started.status_code == 202, started.text
    run_id = started.json()["id"]
    # TestClient roda a background task antes de devolver a resposta
    run = client.get(f"/api/v1/configs/{agent}/eval-runs/{run_id}").json()
    assert run["status"] == "completed", run
    assert (run["total"], run["passed"], run["failed"], run["not_evaluated"]) == (4, 1, 2, 1)
    assert run["version_status"] == "published"

    by_name = {r["case_name"]: r for r in run["results"]}
    assert by_name["prazo"]["status"] == "passed"
    assert by_name["prazo"]["output"] == REPLY
    assert by_name["prazo"]["checks"][0]["rules"] == [
        {"kind": "contains", "value": "30 dias", "passed": True}
    ]
    assert by_name["sem prazo"]["status"] == "failed"
    tools = by_name["busca na base"]
    assert tools["status"] == "failed"
    assert tools["checks"][0] == {
        "type": "tools",
        "passed": False,
        "expected": ["buscar_politicas"],
        "allow_additional": True,
    }
    judge = by_name["só juiz"]
    assert judge["status"] == "not_evaluated"
    assert judge["checks"][0]["passed"] is None
    assert judge["checks"][0]["reason"].startswith("modo demo")
    assert [r["case_name"] for r in run["results"]] == [
        "prazo",
        "sem prazo",
        "busca na base",
        "só juiz",
    ]

    # três casos rodaram o agente: os runs existem, mas ficam fora das conversas
    from app.db import get_engine
    from app.models.run import AgentRun
    from app.models.usage import UsageEvent

    with Session(get_engine()) as session:
        runs = session.scalars(select(AgentRun).where(AgentRun.eval_run_id == uuid.UUID(run_id)))
        assert sorted(r.user_id for r in runs) == ["panel"] * 3
        usage = session.scalars(
            select(UsageEvent).where(UsageEvent.eval_run_id == uuid.UUID(run_id))
        ).all()
        assert sum(u.total_tokens for u in usage) == 30
    assert client.get(f"/api/v1/configs/{agent}/runs").json()["total"] == 0
    assert client.get(f"/api/v1/configs/{agent}/metrics").json()["total_runs"] == 0
    assert client.get("/api/v1/metrics/summary").json()["total_runs"] == 0

    listed = client.get(f"/api/v1/configs/{agent}/eval-runs").json()
    assert [r["id"] for r in listed] == [run_id]


def test_rascunho_por_padrao_e_versao_de_outra_config(client: TestClient) -> None:
    agent = _agent(client, "so rascunho", publish=False)
    other = _agent(client, "outro")
    _case(client, agent, "prazo", [{"type": "text", "kind": "contains", "value": "30 dias"}])

    run = _start(client, agent).json()
    assert run["version_status"] == "draft"

    other_version = client.get(f"/api/v1/configs/{other}").json()["current_version"]["id"]
    resp = _start(client, agent, version_id=other_version)
    assert resp.status_code == 422 and "desta config" in resp.json()["detail"]


def test_sem_casos_execucao_ativa_e_reinicio(client: TestClient) -> None:
    agent = _agent(client, "vazio")
    resp = _start(client, agent)
    assert resp.status_code == 422 and "sem casos" in resp.json()["detail"]

    _case(client, agent, "prazo", [{"type": "text", "kind": "contains", "value": "30 dias"}])
    from app.db import get_engine
    from app.evals.runner import fail_stale
    from app.models.eval import EvalRun

    version = client.get(f"/api/v1/configs/{agent}").json()["current_version"]["id"]
    with Session(get_engine()) as session:
        session.add(
            EvalRun(
                agent_config_id=uuid.UUID(agent),
                version_id=uuid.UUID(version),
                status="running",
                cases=[],
                started_by="alguem",
            )
        )
        session.commit()
    resp = _start(client, agent)
    assert resp.status_code == 409

    assert fail_stale() >= 1
    stale = client.get(f"/api/v1/configs/{agent}/eval-runs").json()[0]
    assert stale["status"] == "failed" and "reinício" in stale["error"]
    assert _start(client, agent).status_code == 202


def test_workflow_nao_roda_suite(client: TestClient) -> None:
    body = {"name": "fluxo", "description": "Use para fluxo", "kind": "workflow"}
    wf = client.post("/api/v1/configs", json=body).json()["id"]
    assert _start(client, wf).status_code == 422


def test_juiz_obrigatorio_e_com_saida_estruturada(client: TestClient) -> None:
    agent = _agent(client, "precisa de juiz")
    _case(client, agent, "tom", [{"type": "judge", "criteria": "Responde com cordialidade"}])
    resp = _start(client, agent)
    assert resp.status_code == 422 and "juiz" in resp.json()["detail"]
    resp = _start(client, agent, judge_model="modelo-inexistente")
    assert resp.status_code == 422 and "não suportado" in resp.json()["detail"]


def test_juiz_avalia_e_consumo_da_execucao(client: TestClient) -> None:
    agent = _agent(client, "com juiz")
    criteria = "Cita o prazo de 30 dias"
    _case(client, agent, "só juiz", [{"type": "judge", "criteria": criteria}])
    _case(
        client,
        agent,
        "texto e juiz",
        [
            {"type": "text", "kind": "contains", "value": "30 dias"},
            {"type": "judge", "criteria": criteria, "mode": "binary"},
        ],
    )
    before = client.get("/api/v1/metrics/summary").json()

    run_id = _start(client, agent, judge_model=JUDGE).json()["id"]
    run = client.get(f"/api/v1/configs/{agent}/eval-runs/{run_id}").json()
    assert run["status"] == "completed", run
    assert (run["passed"], run["failed"], run["not_evaluated"]) == (2, 0, 0)
    assert run["judge_model"] == JUDGE
    judge = run["results"][0]["checks"][0]
    assert judge == {
        "type": "judge",
        "passed": True,
        "criteria": criteria,
        "mode": "binary",
        "score": None,
        "reason": "Cita o prazo de 30 dias.",
    }
    # dois casos de 10 tokens mais o juiz medido nos dois julgamentos
    assert run["total_tokens"] == 2 * 10 + 2 * 7

    after = client.get("/api/v1/metrics/summary").json()
    assert after["eval_tokens"] - before["eval_tokens"] == run["total_tokens"]
    assert after["total_tokens"] == before["total_tokens"]


def _draft(client: TestClient, config_id: str, model_id: str) -> None:
    body = {"name": "x", "description": "Use para x", "payload": {"model_id": model_id}}
    client.put(f"/api/v1/configs/{config_id}/draft", json=body).raise_for_status()


PRAZO = [{"type": "text", "kind": "contains", "value": "30 dias"}]


def test_gate_exige_suite_verde_no_rascunho_atual(client: TestClient) -> None:
    agent = _agent(client, "com gate")
    _case(client, agent, "prazo", PRAZO)
    settings = f"/api/v1/configs/{agent}/eval-settings"
    assert client.get(settings).json()["can_publish"] is True  # gate desligado

    on = client.put(settings, json={"require_passing_evals": True}).json()
    assert on["require_passing_evals"] is True
    assert on["can_publish"] is False and on["reason"] == "não há rascunho para publicar"

    _draft(client, agent, "claude-haiku-4-5")
    status = client.get(settings).json()
    assert status["can_publish"] is False and "não rodou" in status["reason"]
    resp = client.post(f"/api/v1/configs/{agent}/publish")
    assert resp.status_code == 409 and "suíte verde" in resp.json()["detail"]

    run = _start(client, agent).json()
    assert run["version_id"] == status["draft_version_id"]
    status = client.get(settings).json()
    assert status["can_publish"] is True and status["draft_run"]["id"] == run["id"]
    assert client.post(f"/api/v1/configs/{agent}/publish").status_code == 201

    # rascunho novo invalida o resultado; versão que reprova também não publica
    _draft(client, agent, "claude-sonnet-4-6")
    assert client.post(f"/api/v1/configs/{agent}/publish").status_code == 409
    _start(client, agent)
    status = client.get(settings).json()
    assert status["can_publish"] is False and "1 de 1 casos" in status["reason"]
    assert client.post(f"/api/v1/configs/{agent}/publish").status_code == 409

    # rollback não passa pelo gate
    versions = client.get(f"/api/v1/configs/{agent}/versions").json()
    first = next(v for v in versions if v["version_number"] == 2)
    resp = client.post(f"/api/v1/configs/{agent}/rollback", json={"version_id": first["id"]})
    assert resp.status_code == 200, resp.text


def test_comparacao_aponta_regressao(client: TestClient) -> None:
    agent = _agent(client, "comparado")
    _case(client, agent, "prazo", PRAZO)
    _case(client, agent, "cordial", [{"type": "text", "kind": "not_contains", "value": "grosso"}])
    current = client.get(f"/api/v1/configs/{agent}").json()["current_version"]["id"]
    base = _start(client, agent, version_id=current).json()["id"]
    _draft(client, agent, "claude-sonnet-4-6")
    target = _start(client, agent).json()["id"]

    resp = client.get(
        f"/api/v1/configs/{agent}/eval-runs/compare", params={"base": base, "target": target}
    )
    assert resp.status_code == 200, resp.text
    comparison = resp.json()
    assert (comparison["regressions"], comparison["fixes"]) == (1, 0)
    assert {c["case_name"]: c["change"] for c in comparison["cases"]} == {
        "prazo": "regression",
        "cordial": "same",
    }
    assert comparison["base"]["version_status"] == "published"
    assert comparison["target"]["version_status"] == "draft"

    other = _agent(client, "outra")
    resp = client.get(
        f"/api/v1/configs/{other}/eval-runs/compare", params={"base": base, "target": target}
    )
    assert resp.status_code == 404


def test_alvo_por_apelido_origem_e_verdict(client: TestClient) -> None:
    agent = _agent(client, "alvo por apelido")
    _case(client, agent, "prazo", [{"type": "text", "kind": "contains", "value": "30 dias"}])
    # rascunho com o modelo "piorado": a vigente passa, o rascunho não
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={
            "name": "alvo por apelido",
            "description": "Use para alvo por apelido",
            "payload": {"model_id": "claude-sonnet-4-6"},
        },
    ).raise_for_status()
    config = client.get(f"/api/v1/configs/{agent}").json()

    started = _start(client, agent, target="current")
    assert started.status_code == 202, started.text
    # a resposta sai antes da execução: ainda pendente
    assert (started.json()["trigger"], started.json()["target"]) == ("manual", "current")
    assert started.json()["verdict"] == "pending"
    current = client.get(f"/api/v1/configs/{agent}/eval-runs/{started.json()['id']}").json()
    assert current["version_id"] == config["current_version"]["id"]
    assert current["verdict"] == "passed"

    draft = _start(client, agent, target="draft").json()
    draft = client.get(f"/api/v1/configs/{agent}/eval-runs/{draft['id']}").json()
    assert draft["version_id"] == config["draft_version"]["id"]
    assert (draft["status"], draft["verdict"]) == ("completed", "failed")


def test_alvo_invalido_e_recusado(client: TestClient) -> None:
    agent = _agent(client, "sem rascunho")
    _case(client, agent, "prazo", [{"type": "text", "kind": "contains", "value": "30 dias"}])
    config = client.get(f"/api/v1/configs/{agent}").json()

    both = _start(client, agent, target="current", version_id=config["current_version"]["id"])
    assert both.status_code == 422
    # publicado sem rascunho aberto
    no_draft = _start(client, agent, target="draft")
    assert no_draft.status_code == 422
    assert no_draft.json()["detail"] == "Config sem rascunho para testar"

    unpublished = _agent(client, "nunca publicado", publish=False)
    _case(client, unpublished, "prazo", [{"type": "text", "kind": "contains", "value": "30"}])
    resp = _start(client, unpublished, target="current")
    assert resp.json()["detail"] == "Config sem versão publicada para testar"


def test_caso_com_contexto_roda_os_turnos_anteriores_na_mesma_sessao(client: TestClient) -> None:
    body = {"name": "com contexto", "description": "Use para com contexto"}
    agent = str(client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"])
    client.put(
        f"/api/v1/configs/{agent}/draft", json={**body, "payload": {"model_id": "gpt-4o"}}
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()

    saved = client.post(
        f"/api/v1/configs/{agent}/eval-cases",
        json={
            "name": "lembra do pedido",
            "context": ["oi", "meu pedido é o 123"],
            "input": "qual era o pedido?",
            "checks": [{"type": "text", "kind": "contains", "value": "mensagens: 3"}],
        },
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["context"] == ["oi", "meu pedido é o 123"]
    _case(
        client,
        agent,
        "sem contexto",
        [{"type": "text", "kind": "contains", "value": "mensagens: 1"}],
    )
    too_long = client.post(
        f"/api/v1/configs/{agent}/eval-cases",
        json={
            "name": "contexto demais",
            "context": ["x"] * 6,
            "input": "y",
            "checks": [{"type": "text", "kind": "not_empty"}],
        },
    )
    assert too_long.status_code == 422

    run = _start(client, agent).json()
    run = client.get(f"/api/v1/configs/{agent}/eval-runs/{run['id']}").json()
    assert (run["status"], run["passed"], run["total"]) == ("completed", 2, 2), run
    by_name = {r["case_name"]: r for r in run["results"]}
    assert by_name["lembra do pedido"]["output"] == "mensagens: 3"
    # os turnos de contexto também são runs de teste: ficam fora das conversas
    assert client.get(f"/api/v1/configs/{agent}/runs").json()["total"] == 0
