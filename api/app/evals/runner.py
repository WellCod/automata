"""Execução da suíte de testes de um agente ou time (ADR-0015).

Os casos gravados viram `Case`s do runner de suíte do Agno (`agno.eval.suite`), que
roda um por vez com timeout próprio. Cada caso ganha um agente ou time novo, montado
pela mesma factory dos runs reais a partir da versão pedida. O resultado de cada caso
é gravado assim que ele termina, para o painel acompanhar.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from agno.eval.suite import Case, CaseResult, arun_cases
from agno.scorer.base import Score
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.agents.factory import agent_from, load_team, load_version, team_from
from app.agents.tracking import EvalContext, current_eval_run
from app.agents.workflow_factory import rule_matches
from app.db import get_engine
from app.models.eval import EvalResult, EvalRun
from app.schemas.eval import EvalCaseInput, JudgeCheck, TextCheck, ToolsCheck

logger = logging.getLogger(__name__)

CASE_TIMEOUT_S = 120
JUDGE_NOT_EVALUATED = "juiz não configurado nesta execução"


def _text(content: Any) -> str:
    return "" if content is None else str(content)


class TextScorer:
    """Checagens de texto como `Scorer` do Agno: todas precisam passar."""

    def __init__(self, checks: list[TextCheck]) -> None:
        self._checks = checks

    def verdicts(self, content: str) -> list[dict[str, Any]]:
        return [
            {"kind": c.kind, "value": c.value, "passed": rule_matches(c.rule(), content)}
            for c in self._checks
        ]

    async def ascore(self, run: Any, expected: Any = None) -> Score:
        verdicts = self.verdicts(_text(getattr(run, "content", None)))
        ok = sum(1 for v in verdicts if v["passed"])
        failed = [f"{v['kind']} {v['value']!r}".strip() for v in verdicts if not v["passed"]]
        return Score(
            value=ok / len(verdicts),
            passed=ok == len(verdicts),
            reason=("falhou: " + "; ".join(failed)) if failed else None,
            detail={"checks": verdicts},
        )


@dataclass
class PlannedCase:
    """Caso gravado mais o que o runner do Agno consegue avaliar dele."""

    position: int
    case_id: UUID | None
    name: str
    spec: EvalCaseInput
    agno_case: Case | None
    # checagens que não rodam nesta execução, com o motivo
    skipped: dict[str, str]


def _split(spec: EvalCaseInput) -> tuple[list[TextCheck], ToolsCheck | None, JudgeCheck | None]:
    text = [c for c in spec.checks if isinstance(c, TextCheck)]
    tools = next((c for c in spec.checks if isinstance(c, ToolsCheck)), None)
    judge = next((c for c in spec.checks if isinstance(c, JudgeCheck)), None)
    return text, tools, judge


def plan_case(
    position: int, snapshot: dict[str, Any], config_id: UUID, kind: str, version_id: UUID
) -> PlannedCase:
    spec = EvalCaseInput.model_validate(snapshot)
    text, tools, judge = _split(spec)
    skipped: dict[str, str] = {}
    if judge is not None:
        skipped["judge"] = JUDGE_NOT_EVALUATED
    case_id = UUID(snapshot["id"]) if snapshot.get("id") else None
    if not text and tools is None:
        # o Case do Agno recusa caso sem checagem; nada roda e o caso fica não avaliado
        return PlannedCase(position, case_id, spec.name, spec, None, skipped)
    # instância nova por caso: casos não compartilham sessão, estado nem conexão MCP
    target: dict[str, Any]
    if kind == "team":
        target = {"team": team_from(config_id, load_team(config_id, version_id))}
    else:
        target = {"agent": agent_from(config_id, load_version(config_id, version_id), tracked=True)}
    agno_case = Case(
        name=spec.name,
        input=spec.input,
        timeout_seconds=CASE_TIMEOUT_S,
        expected_tool_calls=tuple(tools.tools) if tools else None,
        allow_additional_tool_calls=tools.allow_additional if tools else True,
        scorer=TextScorer(text) if text else None,
        **target,
    )
    return PlannedCase(position, case_id, spec.name, spec, agno_case, skipped)


def result_from(planned: PlannedCase, result: CaseResult | None) -> EvalResult:
    """Traduz o CaseResult do Agno para uma linha de eval_result."""
    text, tools, judge = _split(planned.spec)
    checks: list[dict[str, Any]] = []
    if text:
        detail = (result.score.detail or {}) if result and result.score else {}
        checks.append(
            {
                "type": "text",
                "passed": result.score.passed if result and result.score else None,
                "rules": detail.get("checks", [{"kind": c.kind, "value": c.value} for c in text]),
            }
        )
    if tools is not None:
        checks.append(
            {
                "type": "tools",
                "passed": result.reliability_passed if result else None,
                "expected": tools.tools,
                "allow_additional": tools.allow_additional,
            }
        )
    if judge is not None:
        checks.append(
            {
                "type": "judge",
                "passed": result.judge_passed if result else None,
                "criteria": judge.criteria,
                "mode": judge.mode,
                "score": result.judge_score if result else None,
                "reason": (result.judge_reason if result else None) or planned.skipped.get("judge"),
            }
        )
    if result is None or result.skipped:
        status = "not_evaluated"
    elif result.error or result.timed_out:
        status = "error"
    else:
        status = "passed" if result.passed else "failed"
    error = None
    if result is not None:
        error = "tempo esgotado" if result.timed_out and not result.error else result.error
    return EvalResult(
        case_id=planned.case_id,
        case_name=planned.name,
        position=planned.position,
        status=status,
        checks=checks,
        output=result.output if result else None,
        tools_called=list(result.tools_called) if result else [],
        duration_ms=int(result.duration_seconds * 1000) if result else None,
        error=error,
        session_id=(result.session_id or None) if result else None,
    )


def _set(run_id: UUID, **values: Any) -> None:
    with Session(get_engine()) as session:
        session.execute(update(EvalRun).where(EvalRun.id == run_id).values(**values))
        session.commit()


def _save_result(run_id: UUID, row: EvalResult) -> None:
    with Session(get_engine()) as session:
        row.eval_run_id = run_id
        session.add(row)
        session.commit()


def _load(run_id: UUID) -> tuple[UUID, str, UUID, str, list[dict[str, Any]]]:
    from app.models.config import AgentConfig

    with Session(get_engine()) as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            raise LookupError(f"eval_run {run_id} não existe")
        config = session.get(AgentConfig, run.agent_config_id)
        assert config is not None
        return run.agent_config_id, config.kind, run.version_id, run.started_by, list(run.cases)


async def execute(run_id: UUID) -> None:
    """Roda a suíte em background; qualquer falha fora dos casos marca a execução como falha."""
    try:
        config_id, kind, version_id, actor, snapshots = await asyncio.to_thread(_load, run_id)
        await asyncio.to_thread(_set, run_id, status="running", started_at=datetime.now(UTC))
        planned = await asyncio.to_thread(
            lambda: [
                plan_case(i, snap, config_id, kind, version_id) for i, snap in enumerate(snapshots)
            ]
        )
    except Exception as exc:
        logger.exception("suíte não iniciou", extra={"eval_run_id": str(run_id)})
        await asyncio.to_thread(
            _set, run_id, status="failed", error=str(exc), finished_at=datetime.now(UTC)
        )
        return

    # só o status: a linha gravada expira no commit e não dá para relê-la fora da sessão
    statuses: list[str] = []
    by_name = {p.name: p for p in planned if p.agno_case is not None}

    def on_case_end(case: Case, result: CaseResult) -> None:
        row = result_from(by_name[case.name], result)
        statuses.append(row.status)
        # gravação curta e síncrona: o painel vê o caso assim que ele termina
        _save_result(run_id, row)

    token = current_eval_run.set(EvalContext(eval_run_id=run_id, actor=actor))
    try:
        for p in planned:
            if p.agno_case is None:
                row = result_from(p, None)
                statuses.append(row.status)
                await asyncio.to_thread(_save_result, run_id, row)
        runnable = [p.agno_case for p in planned if p.agno_case is not None]
        if runnable:
            await arun_cases(runnable, default_timeout=CASE_TIMEOUT_S, on_case_end=on_case_end)
    except Exception as exc:
        logger.exception("suíte falhou", extra={"eval_run_id": str(run_id)})
        await asyncio.to_thread(
            _set, run_id, status="failed", error=str(exc), finished_at=datetime.now(UTC)
        )
        return
    finally:
        current_eval_run.reset(token)

    await asyncio.to_thread(
        _set,
        run_id,
        status="completed",
        total=len(planned),
        passed=statuses.count("passed"),
        failed=statuses.count("failed") + statuses.count("error"),
        not_evaluated=statuses.count("not_evaluated"),
        finished_at=datetime.now(UTC),
    )


def fail_stale() -> int:
    """Execução que estava rodando quando a API reiniciou não termina mais: vira falha."""
    with Session(get_engine()) as session:
        result = session.execute(
            update(EvalRun)
            .where(EvalRun.status.in_(("queued", "running")))
            .values(
                status="failed",
                error="interrompida por reinício da API; rode de novo",
                finished_at=datetime.now(UTC),
            )
        )
        session.commit()
        return int(getattr(result, "rowcount", 0) or 0)
