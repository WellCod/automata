"""Evals do aviso de regressão (ADR-0018): quando avisa e como o receptor confere.

Sem banco e sem rede: rodam em todo PR. Avisar demais silencia o canal; avisar de
menos esconde a regressão. Cada linha é uma sequência que precisa dar o evento certo.
"""

import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest

from app.evals.notify import transition
from app.evals.webhook import body_for, sign


def _run(passed: int, total: int = 2, status: str = "completed") -> SimpleNamespace:
    return SimpleNamespace(passed=passed, total=total, status=status)


VERDE = _run(2)
FALHANDO = _run(1)
QUEBRADA = _run(0, status="failed")


@pytest.mark.parametrize(
    ("previous", "current", "regressions", "expected"),
    [
        (None, VERDE, [], None),
        (None, FALHANDO, [], "suite.failing"),
        (None, QUEBRADA, [], "suite.failing"),
        (VERDE, VERDE, [], None),
        (VERDE, FALHANDO, ["prazo"], "suite.regressed"),
        # caiu sem caso que passava ter falhado: caso novo ou erro da execução
        (VERDE, FALHANDO, [], "suite.failing"),
        (VERDE, QUEBRADA, [], "suite.failing"),
        # falha seguida de falha: silêncio, mesmo com outro caso caindo
        (FALHANDO, FALHANDO, ["outro"], None),
        (QUEBRADA, FALHANDO, [], None),
        (FALHANDO, VERDE, [], "suite.recovered"),
        (QUEBRADA, VERDE, [], "suite.recovered"),
        # não avaliado não é verde: suíte vazia também não
        (VERDE, _run(0, total=0), [], "suite.failing"),
    ],
)
def test_transicoes(
    previous: SimpleNamespace | None,
    current: SimpleNamespace,
    regressions: list[str],
    expected: str | None,
) -> None:
    assert transition(previous, current, regressions) == expected  # type: ignore[arg-type]


def test_receptor_confere_a_assinatura_com_o_segredo() -> None:
    body = body_for("suite.regressed", {"config_name": "atendimento"}, "Suíte regrediu")
    signature = sign("segredo", body)
    expected = hmac.new(b"segredo", body, hashlib.sha256).hexdigest()
    assert signature == f"sha256={expected}"
    # um byte a mais no corpo invalida a assinatura
    assert sign("segredo", body + b" ") != signature
    assert sign("outro", body) != signature


def test_corpo_serve_slack_teams_e_discord() -> None:
    payload = json.loads(body_for("suite.recovered", {"passed": 2}, "Voltou a passar"))
    assert payload["text"] == payload["content"] == "Voltou a passar"
    assert payload["event"] == "suite.recovered" and payload["passed"] == 2
    assert "at" in payload
