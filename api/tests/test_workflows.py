"""Workflows rodando de verdade: sequência, paralelo, condição, loop e erro que para o fluxo."""

import os
from collections.abc import Generator
from typing import Any
from uuid import UUID

import pytest
from agno.models.response import ModelResponse
from alembic.config import Config
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents.replay import ReplayModel
from app.agents.workflow_factory import rule_matches
from app.schemas.workflow import WorkflowRule
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

# cada agente usa um modelo diferente, e o modelo responde um texto fixo
REPLIES = {
    "claude-haiku-4-5": "triagem concluída",
    "claude-sonnet-4-6": "análise técnica ok",
    "gpt-4o-mini": "análise financeira ok",
    "claude-opus-4-7": "consolidado: pronto",
    "o3-mini": "revisão feita",
}


class FailingModel(ReplayModel):
    async def ainvoke(self, *args: Any, **kwargs: Any) -> ModelResponse:
        raise RuntimeError("provedor fora do ar")

    async def ainvoke_stream(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("provedor fora do ar")
        yield  # pragma: no cover


def _model(model_id: str, *_: Any, **__: Any) -> ReplayModel:
    if model_id == "gpt-4o":
        return FailingModel(id=model_id)
    return FixedReplyModel(id=model_id, reply=REPLIES[model_id], tokens=10)


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

        original = factory.resolve_model
        factory.resolve_model = _model  # type: ignore[assignment]
        from app.main import create_app

        with TestClient(
            create_app(auto_provision_dbs=True, enable_auth=False, enable_mcp_server=False)
        ) as c:
            yield c
        factory.resolve_model = original
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


def _publish(client: TestClient, kind: str, name: str, payload: dict[str, Any]) -> str:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = client.post("/api/v1/configs", json={**body, "kind": kind}).json()["id"]
    client.put(
        f"/api/v1/configs/{config_id}/draft", json={**body, "payload": payload}
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    return str(config_id)


def _agent(client: TestClient, name: str, model_id: str) -> str:
    return _publish(client, "agent", name, {"model_id": model_id})


def _step(name: str, agent_id: str, **extra: Any) -> dict[str, Any]:
    return {"type": "step", "name": name, "agent_id": agent_id, **extra}


def _runs(client: TestClient, config_id: str) -> int:
    return int(client.get(f"/api/v1/configs/{config_id}/runs").json()["total"])


def _items(client: TestClient, config_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = client.get(f"/api/v1/configs/{config_id}/runs").json()["items"]
    return items


def _parent_ids(config_id: str) -> list[str | None]:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        return list(
            session.scalars(
                select(AgentRun.parent_run_id)
                .where(AgentRun.agent_config_id == UUID(config_id))
                .order_by(AgentRun.created_at)
            )
        )


def _run(client: TestClient, workflow_id: str, message: str) -> dict[str, Any]:
    resp = client.post(
        f"/workflows/{workflow_id}/runs", data={"message": message, "stream": "false"}
    )
    assert resp.status_code == 200, resp.text
    result: dict[str, Any] = resp.json()
    return result


def test_regras() -> None:
    assert rule_matches(WorkflowRule(kind="contains", value="Reembolso"), "quero REEMBOLSO já")
    assert not rule_matches(WorkflowRule(kind="not_contains", value="x"), "tem x")
    assert rule_matches(WorkflowRule(kind="starts_with", value="urgente"), "  Urgente: pagar")
    assert rule_matches(WorkflowRule(kind="empty"), "   ")
    assert rule_matches(WorkflowRule(kind="not_empty"), "a")
    assert rule_matches(WorkflowRule(), "")


def test_sequencia_paralelo_e_condicao(client: TestClient) -> None:
    triagem = _agent(client, "triagem", "claude-haiku-4-5")
    tecnica = _agent(client, "tecnica", "claude-sonnet-4-6")
    financeira = _agent(client, "financeira", "gpt-4o-mini")
    consolida = _agent(client, "consolida", "claude-opus-4-7")
    revisao = _agent(client, "revisao", "o3-mini")
    wf = _publish(
        client,
        "workflow",
        "atendimento",
        {
            "workflow": {
                "steps": [
                    _step("triagem", triagem),
                    {
                        "type": "parallel",
                        "name": "analises",
                        "branches": [_step("tecnica", tecnica), _step("financeira", financeira)],
                    },
                    _step("consolida", consolida),
                    {
                        "type": "condition",
                        "name": "se reembolso",
                        "rule": {"kind": "contains", "source": "input", "value": "reembolso"},
                        "steps": [_step("revisao", revisao)],
                    },
                ]
            }
        },
    )
    assert wf in [w["id"] for w in client.get("/workflows").json()]

    out = _run(client, wf, "quero reembolso do pedido")
    assert out["status"] == "COMPLETED"
    assert out["content"] == "revisão feita"
    for agent in (triagem, tecnica, financeira, consolida, revisao):
        assert _runs(client, agent) == 1
        # ramos paralelos também: a task do gather herda o contexto
        assert _parent_ids(agent) == [out["run_id"]]

    # consumo do workflow é a soma das etapas, sem usage_event próprio
    [run] = _items(client, wf)
    assert run["run_id"] == out["run_id"]
    assert run["steps"] == 5
    assert run["total_tokens"] == 50
    assert _items(client, triagem)[0]["steps"] is None

    out = _run(client, wf, "qual o status do pedido?")
    assert out["status"] == "COMPLETED"
    assert _runs(client, consolida) == 2
    assert _runs(client, revisao) == 1  # condição falsa pulou a revisão


def test_condicao_na_etapa_anterior_e_loop(client: TestClient) -> None:
    triagem = _agent(client, "triagem-2", "claude-haiku-4-5")
    consolida = _agent(client, "consolida-2", "claude-opus-4-7")
    revisao = _agent(client, "revisao-2", "o3-mini")
    wf = _publish(
        client,
        "workflow",
        "com-loop",
        {
            "workflow": {
                "steps": [
                    _step("triagem", triagem),
                    {
                        "type": "condition",
                        "name": "se concluida",
                        "rule": {"kind": "contains", "value": "concluída"},
                        "steps": [_step("revisao", revisao)],
                        "else_steps": [_step("nao-roda", consolida)],
                    },
                    {
                        "type": "loop",
                        "name": "ate pronto",
                        "steps": [_step("consolida", consolida)],
                        "max_iterations": 3,
                        "until": {"kind": "contains", "value": "pronto"},
                    },
                ]
            }
        },
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "COMPLETED"
    assert _runs(client, revisao) == 1
    # loop para na primeira volta (a resposta já diz "pronto") e o else não rodou
    assert _runs(client, consolida) == 1


def test_etapa_com_erro_para_o_fluxo(client: TestClient) -> None:
    quebrado = _agent(client, "quebrado", "gpt-4o")
    depois = _agent(client, "depois", "claude-haiku-4-5")
    wf = _publish(
        client,
        "workflow",
        "para",
        {"workflow": {"steps": [_step("quebrado", quebrado), _step("depois", depois)]}},
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "ERROR"
    assert "fora do ar" in out["content"]
    assert _runs(client, quebrado) == 1
    assert _runs(client, depois) == 0
    runs = client.get(f"/api/v1/configs/{wf}/runs").json()["items"]
    assert [r["status"] for r in runs] == ["error"]

    stream = client.post(f"/workflows/{wf}/runs", data={"message": "oi", "stream": "true"})
    assert "WorkflowError" in stream.text
    assert _runs(client, depois) == 0
    assert _runs(client, wf) == 2
    # no stream o pai também chega à etapa
    parents = _parent_ids(quebrado)
    assert len(parents) == 2 and all(parents)
    assert {r["run_id"] for r in _items(client, wf)} == set(parents)


def test_etapa_marcada_para_seguir(client: TestClient) -> None:
    quebrado = _agent(client, "quebrado-2", "gpt-4o")
    depois = _agent(client, "depois-2", "claude-haiku-4-5")
    wf = _publish(
        client,
        "workflow",
        "segue",
        {
            "workflow": {
                "steps": [
                    _step("quebrado", quebrado, on_error="continue"),
                    _step("depois", depois),
                ]
            }
        },
    )
    out = _run(client, wf, "oi")
    assert out["status"] == "COMPLETED"
    assert _runs(client, depois) == 1


def _review_workflow(client: TestClient, name: str, review: dict[str, Any]) -> tuple[str, str]:
    analise = _agent(client, f"{name} análise", "claude-sonnet-4-6")
    resposta = _agent(client, f"{name} resposta", "claude-opus-4-7")
    wf = _publish(
        client,
        "workflow",
        name,
        {
            "workflow": {
                "steps": [
                    _step("analise", analise, review=review),
                    _step("resposta", resposta),
                ]
            }
        },
    )
    return wf, analise


def _decide(client: TestClient, wf: str, out: dict[str, Any], **decision: Any) -> dict[str, Any]:
    """Como o painel: lê os requisitos do run, marca o ativo e devolve a lista no continue."""
    import json

    run = client.get(
        f"/workflows/{wf}/runs/{out['run_id']}", params={"session_id": out["session_id"]}
    ).json()
    requirements = run["step_requirements"]
    requirements[-1].update(decision)
    resp = client.post(
        f"/workflows/{wf}/runs/{out['run_id']}/continue",
        data={
            "step_requirements": json.dumps(requirements),
            "session_id": out["session_id"],
            "stream": "false",
        },
    )
    assert resp.status_code == 200, resp.text
    result: dict[str, Any] = resp.json()
    return result


def _workflow_run(config_id: str) -> Any:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models.run import AgentRun

    with Session(get_engine()) as session:
        return session.scalars(select(AgentRun).where(AgentRun.agent_config_id == config_id)).one()


def test_revisao_da_saida_pausa_lista_e_segue_ao_aprovar(client: TestClient) -> None:
    review = {"when": "after", "message": "Confira o valor antes de responder"}
    wf, analise = _review_workflow(client, "reembolso revisado", review)

    out = _run(client, wf, "quero reembolso")
    assert out["status"] == "PAUSED", out
    paused = _workflow_run(wf)
    assert paused.status == "paused"
    [pending] = paused.pending_steps
    assert pending["step_name"] == "analise" and pending["when"] == "after"
    assert pending["output"] == "análise técnica ok"
    assert pending["message"] == "Confira o valor antes de responder"

    [item] = [i for i in client.get("/api/v1/approvals").json() if i["agent_id"] == wf]
    assert item["kind"] == "workflow" and item["tools"] == []
    assert item["steps"][0]["output"] == "análise técnica ok"

    done = _decide(client, wf, out, confirmed=True)
    assert done["status"] == "COMPLETED", done
    assert done["content"] == "consolidado: pronto"
    finished = _workflow_run(wf)
    assert finished.status == "success" and finished.pending_steps is None
    # a etapa depois do continue fica com o mesmo pai
    assert _parent_ids(analise) == [out["run_id"]]
    assert not [i for i in client.get("/api/v1/approvals").json() if i["agent_id"] == wf]


def test_recusa_cancela_ou_refaz_a_etapa(client: TestClient) -> None:
    wf, _ = _review_workflow(
        client, "reembolso recusado", {"when": "before", "on_reject": "cancel"}
    )
    out = _run(client, wf, "quero reembolso")
    assert out["status"] == "PAUSED"
    assert _workflow_run(wf).pending_steps[0]["when"] == "before"
    cancelled = _decide(client, wf, out, confirmed=False)
    assert cancelled["status"] == "CANCELLED", cancelled
    assert _workflow_run(wf).status == "cancelled"

    wf, analise = _review_workflow(
        client, "reembolso refeito", {"when": "after", "on_reject": "retry"}
    )
    out = _run(client, wf, "quero reembolso")
    again = _decide(client, wf, out, confirmed=False, rejection_feedback="faltou o valor")
    # recusa com retry: a etapa roda de novo e pausa outra vez para revisão
    assert again["status"] == "PAUSED", again
    assert _runs(client, analise) == 2
    assert _workflow_run(wf).pending_steps[0]["retry_count"] == 1


def test_revisao_dentro_de_conteiner_e_recusada(client: TestClient) -> None:
    agent = _agent(client, "qualquer", "claude-haiku-4-5")
    body = {"name": "revisão no ramo", "description": "x"}
    wf = client.post("/api/v1/configs", json={**body, "kind": "workflow"}).json()["id"]
    review = {"when": "after"}
    for steps in (
        [
            {
                "type": "parallel",
                "name": "ramos",
                "branches": [_step("a", agent, review=review), _step("b", agent)],
            },
            _step("fim", agent),
        ],
        [{"type": "loop", "name": "voltas", "steps": [_step("a", agent, review=review)]}],
        # o Agno 3.1.8 não pausa etapa dentro de condição
        [
            {
                "type": "condition",
                "name": "se",
                "rule": {"kind": "always"},
                "steps": [_step("a", agent, review=review)],
            }
        ],
    ):
        resp = client.put(
            f"/api/v1/configs/{wf}/draft",
            json={**body, "payload": {"workflow": {"steps": steps}}},
        )
        assert resp.status_code == 422 and "nível principal" in resp.text
    resp = client.put(
        f"/api/v1/configs/{wf}/draft",
        json={
            **body,
            "payload": {
                "workflow": {
                    "steps": [_step("a", agent, review={"when": "before", "on_reject": "retry"})]
                }
            },
        },
    )
    assert resp.status_code == 422 and "revisão da saída" in resp.text


def test_saida_editada_segue_e_fica_no_registro(client: TestClient) -> None:
    wf, analise = _review_workflow(
        client, "reembolso editado", {"when": "after", "on_reject": "retry"}
    )
    out = _run(client, wf, "quero reembolso")
    assert out["status"] == "PAUSED", out
    # recusa com motivo, depois edita: as duas decisões entram no registro, na ordem
    again = _decide(client, wf, out, confirmed=False, rejection_feedback="CPF 529.982.247-25")
    assert again["status"] == "PAUSED", again
    done = _decide(client, wf, out, confirmed=True, edited_output="análise revisada: R$ 210")
    assert done["status"] == "COMPLETED", done
    # o modelo da análise rodou duas vezes (a recusa refez); a edição não chamou de novo
    assert _runs(client, analise) == 2
    steps = {s["step_name"]: s for s in done.get("step_results", [])}
    assert steps["analise"]["content"] == "análise revisada: R$ 210"

    log = client.get(f"/api/v1/runs/{out['run_id']}/reviews").json()
    assert [e["decision"] for e in log] == ["rejected", "edited"]
    assert log[0]["feedback"] == "CPF [CPF removido]"
    assert log[1]["before"] == "análise técnica ok"
    assert log[1]["after"] == "análise revisada: R$ 210"
    assert all(e["step_name"] == "analise" and e["by"] == "desconhecido" for e in log)
    assert client.get("/api/v1/runs/nao-existe/reviews").status_code == 404


def test_revisao_por_volta_pede_outra_e_encerra_o_laco(client: TestClient) -> None:
    rascunho = _agent(client, "rascunho por volta", "claude-sonnet-4-6")
    resposta = _agent(client, "resposta por volta", "claude-opus-4-7")
    wf = _publish(
        client,
        "workflow",
        "laço revisado",
        {
            "workflow": {
                "steps": [
                    {
                        "type": "loop",
                        "name": "rascunhos",
                        "steps": [_step("rascunho", rascunho)],
                        "max_iterations": 3,
                        "review": {"message": "A volta ficou boa?"},
                    },
                    _step("final", resposta),
                ]
            }
        },
    )
    out = _run(client, wf, "escreva o aviso")
    assert out["status"] == "PAUSED", out
    [pending] = _workflow_run(wf).pending_steps
    assert pending["when"] == "loop" and pending["message"] == "A volta ficou boa?"

    again = _decide(client, wf, out, confirmed=False, rejection_feedback="mais curto")
    assert again["status"] == "PAUSED", again
    assert _runs(client, rascunho) == 2
    done = _decide(client, wf, out, confirmed=True)
    assert done["status"] == "COMPLETED", done
    # aprovar a volta encerra o laço: nada de terceira volta, e a etapa final roda
    assert _runs(client, rascunho) == 2
    assert done["content"] == "consolidado: pronto"
    log = client.get(f"/api/v1/runs/{out['run_id']}/reviews").json()
    assert [(e["decision"], e.get("feedback")) for e in log] == [
        ("loop_again", "mais curto"),
        ("loop_done", None),
    ]


def test_revisao_por_volta_so_no_nivel_principal_e_com_uma_etapa(client: TestClient) -> None:
    agent = _agent(client, "volta inválida", "claude-haiku-4-5")
    body = {"name": "laço inválido", "description": "x"}
    wf = client.post("/api/v1/configs", json={**body, "kind": "workflow"}).json()["id"]
    review = {"message": "ok?"}
    loop = {"type": "loop", "name": "voltas", "review": review}
    cases = [
        ([{**loop, "steps": [_step("a", agent), _step("b", agent)]}], "uma etapa só"),
        (
            [
                {
                    **loop,
                    "steps": [
                        {
                            "type": "parallel",
                            "name": "p",
                            "branches": [_step("a", agent), _step("b", agent)],
                        }
                    ],
                },
                _step("fim", agent),
            ],
            "uma etapa só",
        ),
        (
            [
                {
                    "type": "condition",
                    "name": "se",
                    "rule": {"kind": "always"},
                    "steps": [{**loop, "steps": [_step("a", agent)]}],
                }
            ],
            "nível principal",
        ),
    ]
    for steps, expected in cases:
        resp = client.put(
            f"/api/v1/configs/{wf}/draft", json={**body, "payload": {"workflow": {"steps": steps}}}
        )
        assert resp.status_code == 422 and expected in resp.text, resp.text
