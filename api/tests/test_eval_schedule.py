"""Agendamento da suíte com poller próprio (ADR-0016): validação, disparo e réplicas."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.settings import get_settings
from tests.fake_models import FixedReplyModel

REPLY = "Prazo de troca: 30 dias corridos a partir do recebimento."


def _model(model_id: str, *_: Any, **__: Any) -> FixedReplyModel:
    # versão "piorada" para a regressão agendada: perde o prazo
    if model_id == "claude-sonnet-4-6":
        return FixedReplyModel(id=model_id, reply="Não sei informar.", tokens=10)
    return FixedReplyModel(id=model_id, reply=REPLY, tokens=10)


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


def _agent(client: TestClient, name: str) -> str:
    body = {"name": name, "description": f"Use para {name}"}
    config_id = str(client.post("/api/v1/configs", json={**body, "kind": "agent"}).json()["id"])
    client.put(
        f"/api/v1/configs/{config_id}/draft",
        json={**body, "payload": {"model_id": "claude-haiku-4-5"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{config_id}/publish").raise_for_status()
    client.post(
        f"/api/v1/configs/{config_id}/eval-cases",
        json={
            "name": "prazo",
            "input": "Qual o prazo?",
            "checks": [{"type": "text", "kind": "contains", "value": "30 dias"}],
        },
    ).raise_for_status()
    return config_id


def _due(config_id: str) -> None:
    """Põe o próximo horário no passado, como se a hora tivesse chegado."""
    from app.db import get_engine
    from app.models.eval import EvalSchedule

    with Session(get_engine()) as session:
        session.execute(
            update(EvalSchedule)
            .where(EvalSchedule.agent_config_id == config_id)
            .values(next_run_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        session.commit()


@pytest.mark.parametrize(
    ("cron", "tz", "detail"),
    [
        ("*/5 * * * *", "America/Sao_Paulo", "O intervalo mínimo entre execuções é de 1 hora"),
        ("0,30 * * * *", "UTC", "O intervalo mínimo entre execuções é de 1 hora"),
        ("toda hora!", "UTC", "Expressão cron inválida"),
        ("0 * * * *", "Lua/Base", "Fuso horário desconhecido: Lua/Base"),
    ],
)
def test_agendamento_invalido_e_recusado(
    client: TestClient, cron: str, tz: str, detail: str
) -> None:
    agent = _agent(client, f"invalido {cron} {tz}")
    resp = client.put(
        f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": cron, "timezone": tz}
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"] == detail


def test_agendamento_dispara_uma_vez_por_horario(client: TestClient) -> None:
    from app.evals import scheduler

    agent = _agent(client, "diario")
    saved = client.put(f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": "0 9 * * *"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["target"] == "current"
    assert datetime.fromisoformat(saved.json()["next_run_at"]) > datetime.now(UTC)
    # ainda não venceu: nada roda
    assert scheduler.poll_once() == []

    _due(agent)
    started = scheduler.poll_once()
    assert len(started) == 1
    # o próximo horário já andou: a segunda passada não duplica
    assert scheduler.poll_once() == []

    run = client.get(f"/api/v1/configs/{agent}/eval-runs/{started[0]}").json()
    assert (run["trigger"], run["target"], run["started_by"]) == (
        "schedule",
        "current",
        "agendamento",
    )
    schedule = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    assert schedule["last_run_id"] == str(started[0])
    assert schedule["last_error"] is None
    assert datetime.fromisoformat(schedule["next_run_at"]) > datetime.now(UTC)


def test_duas_replicas_nao_duplicam(client: TestClient) -> None:
    from app.db import get_engine
    from app.evals import scheduler
    from app.models.eval import EvalSchedule

    agent = _agent(client, "replicas")
    client.put(f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": "0 */6 * * *"})
    _due(agent)
    # a primeira réplica trava a linha e ainda não fez commit
    with Session(get_engine()) as first:
        locked = first.scalars(
            select(EvalSchedule)
            .where(EvalSchedule.agent_config_id == agent)
            .with_for_update(skip_locked=True)
        ).all()
        assert len(locked) == 1
        # a segunda pula a linha travada
        assert scheduler.poll_once() == []
        first.rollback()
    assert len(scheduler.poll_once()) == 1


def test_horario_recusado_registra_o_motivo_e_segue(client: TestClient) -> None:
    from app.evals import scheduler

    agent = _agent(client, "sem casos depois")
    client.put(f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": "0 9 * * 1-5"})
    case = client.get(f"/api/v1/configs/{agent}/eval-cases").json()[0]
    client.delete(f"/api/v1/configs/{agent}/eval-cases/{case['id']}").raise_for_status()
    _due(agent)

    assert scheduler.poll_once() == []
    schedule = client.get(f"/api/v1/configs/{agent}/eval-schedule").json()
    assert schedule["last_error"] == "Suíte sem casos"
    assert schedule["last_attempt_at"] is not None
    assert datetime.fromisoformat(schedule["next_run_at"]) > datetime.now(UTC)


def test_desligar_e_apagar(client: TestClient) -> None:
    from app.evals import scheduler

    agent = _agent(client, "desligado")
    off = client.put(
        f"/api/v1/configs/{agent}/eval-schedule",
        json={"cron_expr": "0 9 * * *", "enabled": False},
    ).json()
    assert off["next_run_at"] is None
    assert scheduler.poll_once() == []

    assert client.delete(f"/api/v1/configs/{agent}/eval-schedule").status_code == 204
    assert client.get(f"/api/v1/configs/{agent}/eval-schedule").status_code == 404


def _tick(agent: str) -> str:
    """Um horário vencido: o poller cria a execução e ela roda até o fim."""
    import asyncio

    from app.evals import scheduler
    from app.evals.runner import execute

    _due(agent)
    started = scheduler.poll_once()
    assert len(started) == 1
    asyncio.run(execute(started[0]))
    return str(started[0])


def _status(client: TestClient, agent: str) -> dict[str, Any]:
    states = {s["config_id"]: s for s in client.get("/api/v1/eval-status").json()}
    return states[agent]


def test_regressao_agendada_aparece_no_estado_da_suite(client: TestClient) -> None:
    agent = _agent(client, "regride")
    client.put(f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": "0 8 * * *"})

    first = _tick(agent)
    status = _status(client, agent)
    assert (status["state"], status["regressions"]) == ("passing", 0)
    assert status["last_run"]["id"] == first

    # a vigente muda por fora do teste (aqui, o modelo) e perde o prazo
    body = {"name": "regride", "description": "Use para regride"}
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={**body, "payload": {"model_id": "claude-sonnet-4-6"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()

    second = _tick(agent)
    status = _status(client, agent)
    assert (status["state"], status["regressions"]) == ("regressed", 1)
    assert (status["last_run"]["id"], status["previous_run_id"]) == (second, first)
    compared = client.get(
        f"/api/v1/configs/{agent}/eval-runs/compare", params={"base": first, "target": second}
    ).json()
    assert [c["change"] for c in compared["cases"]] == ["regression"]


def test_falha_sem_passado_verde_e_so_falhando(client: TestClient) -> None:
    agent = _agent(client, "sempre falhou")
    body = {"name": "sempre falhou", "description": "Use para sempre falhou"}
    client.put(
        f"/api/v1/configs/{agent}/draft",
        json={**body, "payload": {"model_id": "claude-sonnet-4-6"}},
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent}/publish").raise_for_status()
    client.put(f"/api/v1/configs/{agent}/eval-schedule", json={"cron_expr": "0 8 * * *"})

    _tick(agent)
    _tick(agent)
    status = _status(client, agent)
    assert (status["state"], status["regressions"]) == ("failing", 0)
