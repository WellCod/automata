"""Evals da operação: retry da fila, conciliação de custo e aviso por e-mail (ADR-0037).

Sem banco e sem rede. Errar o retry é repetir sozinho um run que paga boleto, ou deixar
cair calado o run que podia repetir. Errar a conciliação é ler centavos como dólares.
Errar o e-mail é vazar a senha do SMTP no status do destino.
"""

import time
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app import job_queue, mailer
from app.reconciliation import fetch_anthropic, fetch_openai

NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)


def _job(job_id: str, config: str, attempt: int, age_s: int = 60) -> dict[str, Any]:
    stamp = int(NOW.timestamp()) - age_s
    return {
        "id": job_id,
        "component_id": config,
        "attempt": attempt,
        "status": "failed",
        "error": "boom",
        "completed_at": stamp,
        "updated_at": stamp,
    }


@pytest.mark.parametrize(
    ("retries", "attempt", "expected"),
    [
        (0, 1, "job.failed"),  # sem a opção, nunca repete
        (1, 1, "requeued"),
        (1, 2, "job.failed"),  # esgotou
        (2, 2, "requeued"),
        (2, 3, "job.failed"),
    ],
)
def test_decisao_do_retry(
    monkeypatch: pytest.MonkeyPatch, retries: int, attempt: int, expected: str
) -> None:
    import app.alerts as alerts

    config = "11111111-1111-1111-1111-111111111111"
    requeued: list[str] = []

    class FakeDb:
        def list_jobs(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
            return [_job("j1", config, attempt)], 1

    monkeypatch.setattr(job_queue, "durable", lambda: True)
    monkeypatch.setattr(job_queue, "jobs_db", lambda: FakeDb())
    monkeypatch.setattr(job_queue, "retries_by_config", lambda s, ids: {config: retries})
    monkeypatch.setattr(job_queue, "config_names", lambda s, ids: {config: "agente"})
    monkeypatch.setattr(job_queue, "requeue", lambda job_id: requeued.append(job_id) or True)
    monkeypatch.setattr(alerts, "destinations_for", lambda s, e: [object()])
    monkeypatch.setattr(alerts, "claim", lambda *a: True)
    monkeypatch.setattr(alerts, "broadcast", lambda *a: 1)
    assert dict(job_queue.check_jobs(None, NOW))["j1"] == expected  # type: ignore[arg-type]
    assert bool(requeued) is (expected == "requeued")


def test_falha_antiga_nao_acorda_no_deploy(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDb:
        def list_jobs(self, **kwargs: Any) -> tuple[list[dict[str, Any]], int]:
            return [_job("velho", "c", 1, age_s=2 * 86400)], 1

    monkeypatch.setattr(job_queue, "durable", lambda: True)
    monkeypatch.setattr(job_queue, "jobs_db", lambda: FakeDb())
    assert job_queue.check_jobs(None, NOW) == []  # type: ignore[arg-type]


def _pages(*bodies: dict[str, Any]) -> httpx.Client:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(1)
        return httpx.Response(200, json=bodies[len(seen) - 1])

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("amounts", "dollars"),
    [
        (["100"], Decimal("1")),
        (["0.5", "0.5"], Decimal("0.01")),
        (["123.78912"], Decimal("1.2378912")),
        ([], Decimal(0)),
    ],
)
def test_anthropic_e_centavos(amounts: list[str], dollars: Decimal) -> None:
    body = {
        "data": [
            {"starting_at": "2026-11-02T00:00:00Z", "results": [{"amount": a} for a in amounts]}
        ],
        "has_more": False,
    }
    days = fetch_anthropic("k", date(2026, 11, 2), date(2026, 11, 3), _pages(body))
    assert days[date(2026, 11, 2)] == dollars


def test_openai_e_dolares_e_soma_os_itens() -> None:
    start = int(datetime(2026, 11, 2, tzinfo=UTC).timestamp())
    body = {
        "data": [
            {
                "start_time": start,
                "results": [{"amount": {"value": 1.5}}, {"amount": {"value": 0.25}}, {}],
            }
        ],
        "has_more": False,
    }
    days = fetch_openai("k", date(2026, 11, 2), date(2026, 11, 3), _pages(body))
    assert days[date(2026, 11, 2)] == Decimal("1.75")


def test_status_do_email_nunca_traz_a_mensagem_do_servidor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Boom:
        def __init__(self, *a: Any, **k: Any) -> None:
            raise OSError("535 auth failed for user=avisos password=segredo123")

    monkeypatch.setenv("SMTP_HOST", "smtp.x")
    monkeypatch.setattr(mailer.smtplib, "SMTP", Boom)
    status = mailer.send(["a@b.com"], "s", "t")
    assert status == "falhou: OSError" and "segredo123" not in status


def test_sem_smtp_recusa_sem_tentar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SMTP_HOST", raising=False)
    started = time.perf_counter()
    assert mailer.send(["a@b.com"], "s", "t").startswith("recusado")
    assert time.perf_counter() - started < 0.5
