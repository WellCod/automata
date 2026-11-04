"""Evals dos direitos do titular e da máscara com padrões próprios (ADR-0032).

Errar a exclusão é deixar dado de quem pediu para sair, apagar dado de outra pessoa
ou mudar as métricas e o custo para trás. Errar a máscara é mandar matrícula e
contrato inteiros para o modelo e para a memória, ou travar a API com o regex.
"""

import gzip
import json
import os
import time
from collections.abc import Generator
from decimal import Decimal
from typing import Any

import pytest
from agno.db.postgres import PostgresDb
from agno.db.schemas.memory import UserMemory
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.agents import memory
from app.agents.replay import ReplayModel
from app.guardrails.pii import CustomPattern, find_pii, mask
from app.schemas.config import MemorySettings
from app.settings import get_settings

ANA = "ana@cliente.com"
BIA = "bia@cliente.com"
# id com aspas e ponto e vírgula: a exclusão usa parâmetro, nunca texto montado
ODD = "o'brien; drop table agent_run --"

MAT = CustomPattern("matrícula", "MAT", 6, 8)
CONTRATO = CustomPattern("contrato", "CT", 8, 12)
PROTOCOLO = CustomPattern("protocolo", "", 14, 14)

# --- máscara com padrões próprios (sem banco) ---


@pytest.mark.parametrize(
    ("text", "leaked"),
    [
        ("minha matrícula é MAT-1234567", "1234567"),
        ("mat 12.345.678 por favor", "12.345.678"),
        ("contrato CT 2024/00012345", "2024/00012345"),
        ("ct:000123456789", "000123456789"),
        ("protocolo 2024 1104 1234 56", "2024 1104 1234 56"),
    ],
)
def test_padrao_proprio_nunca_passa_inteiro(text: str, leaked: str) -> None:
    masked = mask(text, find_pii(text, custom=[MAT, CONTRATO, PROTOCOLO]))
    assert leaked not in masked
    assert "removido]" in masked


@pytest.mark.parametrize(
    "text",
    [
        "pedido 12345",  # número curto sem prefixo
        "MATRIZ 1234567",  # prefixo dentro de outra palavra
        "o CT-123 venceu",  # dígitos de menos
        "fone 2024-11-04",  # data não é protocolo de 14 dígitos
    ],
)
def test_padrao_proprio_nao_pega_o_que_nao_e(text: str) -> None:
    assert find_pii(text, types=[], custom=[MAT, CONTRATO, PROTOCOLO]) == []


def test_documento_continua_com_o_rotulo_do_documento() -> None:
    text = "CPF 529.982.247-25 e cartão 4111 1111 1111 1111"
    masked = mask(text, find_pii(text, custom=[CustomPattern("conta", "", 11, 16)]))
    assert masked == "CPF [CPF removido] e cartão [cartão removido]"


def test_dez_padroes_em_texto_hostil_no_teto_do_scan() -> None:
    patterns = [CustomPattern(f"p{i}", f"P{i}", 4, 20) for i in range(9)] + [
        CustomPattern("solto", "", 4, 20)
    ]
    hostile = ["1-" * 50_000, "P1 " * 33_000, "P1-" + "1." * 49_000, "9" * 100_000]
    started = time.perf_counter()
    for text in hostile:
        find_pii(text, custom=patterns)
    assert time.perf_counter() - started < 3


def test_memoria_mascara_com_os_padroes_do_agente_que_gravou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # sem banco: a gravação do Agno devolve a memória que receberia
    monkeypatch.setattr(PostgresDb, "upsert_user_memory", lambda self, m, *a, **k: m)
    monkeypatch.setattr(memory, "_custom_by_agent", {})
    monkeypatch.setattr(memory, "memory_db", lambda: None)
    memory.memory_kwargs("agente-a", MemorySettings(enabled=True), "u", (MAT,))
    memory.memory_kwargs("agente-b", MemorySettings(enabled=True), "u")
    db = memory.MaskingDb.__new__(memory.MaskingDb)

    saved_a = db.upsert_user_memory(
        UserMemory(memory="matrícula MAT 1234567", input="sou MAT 1234567", agent_id="agente-a")
    )
    assert "1234567" not in saved_a.memory and "1234567" not in saved_a.input
    saved_b = db.upsert_user_memory(UserMemory(memory="matrícula MAT 1234567", agent_id="agente-b"))
    assert saved_b.memory == "matrícula MAT 1234567"
    # documento sai em qualquer agente, com ou sem padrão próprio
    saved_c = db.upsert_user_memory(UserMemory(memory="CPF 52998224725", agent_id="agente-b"))
    assert "52998224725" not in saved_c.memory


# --- exclusão (com banco) ---


@pytest.fixture(scope="module")
def db_url() -> Generator[str, None, None]:
    with PostgresContainer("pgvector/pgvector:pg17") as pg:
        url = pg.get_connection_url().replace("psycopg2", "psycopg")
        os.environ["DATABASE_URL"] = url
        os.environ.setdefault("JWT_PRIVATE_KEY", "x")
        os.environ.setdefault("JWT_PUBLIC_KEY", "x")
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        yield url
        os.environ.pop("DATABASE_URL", None)
        get_settings.cache_clear()


@pytest.fixture(scope="module")
def client(db_url: str) -> Generator[TestClient, None, None]:
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


def _agent(client: TestClient) -> str:
    created = client.post("/api/v1/configs", json={"name": "atendimento", "description": "x"})
    agent_id = str(created.json()["id"])
    client.put(
        f"/api/v1/configs/{agent_id}/draft",
        json={
            "name": "atendimento",
            "description": "x",
            "payload": {"model_id": "claude-haiku-4-5"},
        },
    ).raise_for_status()
    client.post(f"/api/v1/configs/{agent_id}/publish").raise_for_status()
    return agent_id


def _talk(client: TestClient, agent_id: str, user: str, message: str) -> None:
    resp = client.post(
        f"/agents/{agent_id}/runs",
        data={"message": message, "stream": "false", "user_id": user},
    )
    assert resp.status_code == 200, resp.text


def _numbers(client: TestClient, agent_id: str) -> tuple[Any, ...]:
    summary = client.get("/api/v1/metrics/summary").json()
    agent = client.get(f"/api/v1/configs/{agent_id}/metrics").json()
    return (
        summary["total_runs"],
        summary["total_tokens"],
        summary["total_cost"],
        agent["total_runs"],
        agent["blocked_runs"],
    )


def test_exclusao_completa_isolada_e_sem_mudar_os_numeros(client: TestClient, db_url: str) -> None:
    from app.db import get_engine
    from app.models.caller_budget import CallerBudget
    from app.models.run import AgentRun

    agent_id = _agent(client)
    for user in (ANA, ANA, BIA, ODD):
        _talk(client, agent_id, user, f"pedido de {user}")
    agno = PostgresDb(db_url=db_url)
    agno.upsert_user_memory(UserMemory(memory="ana prefere a tarde", user_id=ANA))
    agno.upsert_user_memory(UserMemory(memory="bia mora em Recife", user_id=BIA))
    with Session(get_engine()) as session:
        ana_run = session.scalars(select(AgentRun.run_id).where(AgentRun.user_id == ANA)).first()
        session.add(CallerBudget(subject=ANA, monthly_usd=Decimal("5"), updated_by="t"))
        session.commit()
    case = client.post(
        f"/api/v1/configs/{agent_id}/eval-cases",
        json={
            "name": "da conversa",
            "input": "pedido",
            "checks": [{"type": "text", "kind": "not_empty"}],
            "source_run_id": ana_run,
        },
    )
    assert case.status_code == 201, case.text
    pending_export = client.post(f"/api/v1/data-subjects/{ANA}/export").json()["id"]

    before = _numbers(client, agent_id)
    bia_before = client.get(f"/api/v1/data-subjects/{BIA}").json()
    ana = client.get(f"/api/v1/data-subjects/{ANA}").json()
    assert ana["counts"]["sessions"] >= 1 and ana["counts"]["memories"] == 1

    erased = client.post(f"/api/v1/data-subjects/{ANA}/erase", json={"confirm": ANA})
    assert erased.status_code == 202, erased.text

    # nada da Ana, nada da Bia mexido, números iguais
    assert client.get(f"/api/v1/data-subjects/{ANA}").json()["total"] == 0
    assert client.get(f"/api/v1/data-subjects/{BIA}").json() == bia_before
    assert _numbers(client, agent_id) == before
    cases = client.get(f"/api/v1/configs/{agent_id}/eval-cases").json()
    [kept] = [c for c in cases if c["id"] == case.json()["id"]]
    assert kept["source_run_id"] is None
    with Session(get_engine()) as session:
        assert session.get(CallerBudget, ANA) is None

    # a exportação pedida antes perdeu o arquivo e o id em claro
    requests = client.get("/api/v1/data-subject-requests").json()
    [export] = [r for r in requests if r["id"] == pending_export]
    assert export["subject"] is None
    assert client.get(f"/api/v1/data-subject-requests/{pending_export}/download").status_code == 409
    assert ANA not in json.dumps(requests)

    # de novo: nada a apagar, sem erro
    again = client.post(f"/api/v1/data-subjects/{ANA}/erase", json={"confirm": ANA}).json()
    [row] = [
        r for r in client.get("/api/v1/data-subject-requests").json() if r["id"] == again["id"]
    ]
    assert row["status"] == "done"
    assert sum(v for v in row["counts"].values() if isinstance(v, int)) == 0


def test_id_estranho_e_parametro_e_nao_vaza_na_exportacao(client: TestClient) -> None:
    from urllib.parse import quote

    path = quote(ODD, safe="")
    export_id = client.post(f"/api/v1/data-subjects/{path}/export").json()["id"]
    download = client.get(f"/api/v1/data-subject-requests/{export_id}/download")
    assert download.status_code == 200
    data = json.loads(gzip.decompress(download.content))
    assert {s["user_id"] for s in data["agno"]["sessions"]} == {ODD}
    assert BIA not in json.dumps(data, ensure_ascii=False)

    resp = client.post(f"/api/v1/data-subjects/{path}/erase", json={"confirm": ODD})
    assert resp.status_code == 202
    assert client.get(f"/api/v1/data-subjects/{path}").json()["total"] == 0
    assert client.get(f"/api/v1/data-subjects/{BIA}").json()["total"] > 0
