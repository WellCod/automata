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
from tests.fake_models import FixedReplyModel

REPLY = "Prazo de troca: 30 dias corridos a partir do recebimento."


JUDGE = "gpt-4o-mini"
VERDICT = '{"passed": true, "reason": "Cita o prazo de 30 dias."}'


def _model(model_id: str, *_: Any, **__: Any) -> ReplayModel:
    # o juiz responde no schema binário do AgentAsJudgeEval
    if model_id == JUDGE:
        return FixedReplyModel(id=model_id, reply=VERDICT, tokens=7)
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
