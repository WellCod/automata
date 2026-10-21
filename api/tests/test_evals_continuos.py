"""Evals dos evals contínuos (ADR-0016): quem pode rodar, quando roda e o que o pipeline lê.

Sem LLM e sem banco: rodam em todo PR. Cobrem as decisões que, se mudarem em
silêncio, deixam um token rodar a suíte de outro agente, um agendamento rodar a
cada minuto ou um CI passar com caso não avaliado.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.authz import require_resource_scope
from app.evals.scheduler import next_run, validate
from app.integrations import integration_scopes
from app.routers.evals import verdict

MIN = "O intervalo mínimo entre execuções é de 1 hora"


@dataclass(frozen=True)
class CronCase:
    cron: str
    tz: str
    reason: str | None


CRON_CASES = [
    CronCase("0 * * * *", "UTC", None),
    CronCase("0 8 * * 1-5", "America/Sao_Paulo", None),
    CronCase("30 */6 * * *", "America/Sao_Paulo", None),
    CronCase("0 0 29 2 *", "UTC", None),
    CronCase("*/30 * * * *", "UTC", MIN),
    CronCase("0,59 * * * *", "UTC", MIN),
    # dois horários no mesmo dia, com 10 minutos entre eles
    CronCase("0,10 8 * * *", "UTC", MIN),
    CronCase("", "UTC", "Expressão cron inválida"),
    CronCase("toda segunda", "UTC", "Expressão cron inválida"),
    CronCase("0 8 * * *", "Brasil/Brasilia", "Fuso horário desconhecido: Brasil/Brasilia"),
]


@pytest.mark.parametrize("case", CRON_CASES, ids=lambda c: f"{c.cron or 'vazio'}@{c.tz}")
def test_validacao_do_agendamento(case: CronCase) -> None:
    assert validate(case.cron, case.tz) == case.reason


def test_proximo_horario_respeita_o_fuso() -> None:
    # 8h em São Paulo (UTC-3, sem horário de verão) é 11h UTC
    after = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
    assert next_run("0 8 * * *", "America/Sao_Paulo", after) == datetime(
        2026, 11, 4, 11, 0, tzinfo=UTC
    )


def _request(scopes: list[str], config_id: str, enforce: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(enforce_scopes=enforce)),
        state=SimpleNamespace(scopes=scopes, admin_scope="agent_os:admin"),
        path_params={"config_id": config_id},
    )


ALVO = str(uuid4())
OUTRO = str(uuid4())


@pytest.mark.parametrize(
    ("scopes", "config_id", "action", "allowed"),
    [
        # token de integração: só o config liberado, só rodar e ler
        ([f"evals:{ALVO}:run", f"evals:{ALVO}:read"], ALVO, "run", True),
        ([f"evals:{ALVO}:run", f"evals:{ALVO}:read"], OUTRO, "run", False),
        ([f"evals:{ALVO}:read"], ALVO, "run", False),
        ([f"agents:{ALVO}:run"], ALVO, "run", False),
        # papéis do painel: escopo global
        (["evals:run", "evals:read"], OUTRO, "run", True),
        (["evals:read"], OUTRO, "read", True),
        (["evals:read"], OUTRO, "run", False),
        (["agent_os:admin"], OUTRO, "run", True),
        ([], ALVO, "read", False),
    ],
)
def test_escopo_por_recurso(scopes: list[str], config_id: str, action: str, allowed: bool) -> None:
    check = require_resource_scope("evals", action)
    if allowed:
        check(_request(scopes, config_id))  # type: ignore[arg-type]
    else:
        with pytest.raises(HTTPException) as exc:
            check(_request(scopes, config_id))  # type: ignore[arg-type]
        assert exc.value.status_code == 403


def test_sem_auth_nao_checa() -> None:
    require_resource_scope("evals", "run")(_request([], ALVO, enforce=False))  # type: ignore[arg-type]


def test_token_com_suite_nao_ganha_escrita() -> None:
    config = uuid4()
    scopes = integration_scopes([], [], [config])
    assert scopes == [f"evals:{config}:read", f"evals:{config}:run"]
    assert not any(s.endswith(":write") for s in scopes)


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"status": "queued"}, "pending"),
        ({"status": "running"}, "pending"),
        ({"status": "completed", "total": 3, "passed": 3}, "passed"),
        # não avaliado (juiz no modo demo) não é aprovado: o pipeline falha
        ({"status": "completed", "total": 3, "passed": 2}, "failed"),
        ({"status": "completed", "total": 0, "passed": 0}, "failed"),
        ({"status": "failed", "total": 3, "passed": 3}, "failed"),
    ],
)
def test_verdict_que_o_pipeline_le(fields: dict[str, object], expected: str) -> None:
    run = SimpleNamespace(**{"total": 0, "passed": 0, **fields})
    assert verdict(run) == expected  # type: ignore[arg-type]
