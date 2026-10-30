"""Execução da suíte de testes de um agente, time ou workflow (ADR-0015, ADR-0022).

Os casos gravados viram `Case`s do runner de suíte do Agno (`agno.eval.suite`), que
roda um por vez com timeout próprio. Cada caso ganha um agente ou time novo, montado
pela mesma factory dos runs reais a partir da versão pedida. O resultado de cada caso
é gravado assim que ele termina, para o painel acompanhar.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from agno.eval.suite import Case, CaseResult, JudgeMode, arun_cases
from agno.scorer.base import Score
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.agents import models_map
from app.agents.factory import agent_from, load_team, load_version, team_from
from app.agents.output_schema import schema_verdict
from app.agents.tracking import EvalContext, TrackedWorkflow, current_eval_run
from app.agents.workflow_factory import build_nodes, load_workflow, rule_matches
from app.budget import RULE_BUDGET
from app.db import get_db, get_engine
from app.evals.judge import JudgeUsage, metered
from app.evals.workflow_case import WorkflowUnderTest
from app.guardrails.input import BlockLog
from app.models.eval import EvalResult, EvalRun
from app.models.usage import UsageEvent
from app.pricing import cost_or_estimate
from app.repositories.usage import UsageRepository
from app.schemas.eval import (
    BlockedCheck,
    EvalCaseInput,
    JudgeCheck,
    SchemaCheck,
    StepsCheck,
    TextCheck,
    ToolsCheck,
)

logger = logging.getLogger(__name__)

CASE_TIMEOUT_S = 120
# cada mensagem de contexto roda no setup do Case, que fica fora do timeout do caso
CONTEXT_TIMEOUT_S = 60
JUDGE_IN_DEMO = "modo demo: o juiz não roda com respostas gravadas"
JUDGE_WITHOUT_MODEL = "execução sem modelo de juiz"


def _text(content: Any) -> str:
    if isinstance(content, dict | list):
        # saída estruturada: as regras de texto valem sobre o JSON
        return json.dumps(content, ensure_ascii=False)
    return "" if content is None else str(content)


def steps_verdict(check: StepsCheck, ran: list[str]) -> dict[str, Any]:
    missing = [name for name in check.steps if name not in ran]
    extra = sorted({name for name in ran if name not in check.steps}) if check.exclusive else []
    return {"ran": ran, "missing": missing, "extra": extra, "passed": not missing and not extra}


class TextScorer:
    """Checagens de texto, e de etapas no workflow, como `Scorer` do Agno: todas precisam passar."""

    def __init__(
        self,
        checks: list[TextCheck],
        steps: StepsCheck | None = None,
        schema: dict[str, Any] | None = None,
    ) -> None:
        self._checks = checks
        self._steps = steps
        # o JSON Schema da versão testada, quando o caso tem a checagem `schema`
        self._schema = schema

    def verdicts(self, content: str) -> list[dict[str, Any]]:
        return [
            {"kind": c.kind, "value": c.value, "passed": rule_matches(c.rule(), content)}
            for c in self._checks
        ]

    async def ascore(self, run: Any, expected: Any = None) -> Score:
        verdicts = self.verdicts(_text(getattr(run, "content", None)))
        ok = sum(1 for v in verdicts if v["passed"])
        total = len(verdicts)
        failed = [f"{v['kind']} {v['value']!r}".strip() for v in verdicts if not v["passed"]]
        detail: dict[str, Any] = {"checks": verdicts}
        if self._steps is not None:
            ran = list((getattr(run, "metadata", None) or {}).get("steps", []))
            steps = steps_verdict(self._steps, ran)
            detail["steps"] = steps
            total += 1
            ok += steps["passed"]
            if steps["missing"]:
                failed.append("não rodou " + ", ".join(steps["missing"]))
            if steps["extra"]:
                failed.append("rodou fora da lista " + ", ".join(steps["extra"]))
        if self._schema is not None:
            verdict = schema_verdict(self._schema, getattr(run, "content", None))
            detail["schema"] = verdict
            total += 1
            ok += verdict["passed"]
            if not verdict["passed"]:
                failed.append("fora do schema: " + "; ".join(verdict["errors"]))
        return Score(
            value=ok / total,
            passed=ok == total,
            reason=("falhou: " + "; ".join(failed)) if failed else None,
            detail=detail,
        )


class AnsweredScorer:
    """Caso que espera bloqueio: o Agno só chama o scorer em run completo, que é o que reprova."""

    async def ascore(self, run: Any, expected: Any = None) -> Score:
        return Score(value=0.0, passed=False, reason="respondeu sem bloquear")


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
    # bloqueios do run do caso, para a checagem `blocked` (ADR-0022)
    blocks: BlockLog | None = None


def _split(spec: EvalCaseInput) -> tuple[list[TextCheck], ToolsCheck | None, JudgeCheck | None]:
    text = [c for c in spec.checks if isinstance(c, TextCheck)]
    tools = next((c for c in spec.checks if isinstance(c, ToolsCheck)), None)
    judge = next((c for c in spec.checks if isinstance(c, JudgeCheck)), None)
    return text, tools, judge


def _blocked(spec: EvalCaseInput) -> BlockedCheck | None:
    return next((c for c in spec.checks if isinstance(c, BlockedCheck)), None)


def _steps(spec: EvalCaseInput) -> StepsCheck | None:
    return next((c for c in spec.checks if isinstance(c, StepsCheck)), None)


def _schema_check(spec: EvalCaseInput) -> SchemaCheck | None:
    return next((c for c in spec.checks if isinstance(c, SchemaCheck)), None)


NO_SCHEMA = "a versão testada não tem saída estruturada"


def _runner_for(config_id: UUID, kind: str, version_id: UUID, actor: str) -> tuple[str, Any]:
    """Instância nova por caso: casos não compartilham sessão, estado nem conexão MCP."""
    if kind == "workflow":
        resolved = load_workflow(config_id, version_id)
        workflow = TrackedWorkflow(
            id=str(config_id),
            name=resolved.name,
            description=resolved.description,
            steps=build_nodes(resolved.steps, resolved),
            user_id=actor,
        )
        workflow.automata_config_id = config_id
        return "agent", WorkflowUnderTest(workflow, set(resolved.executors))
    if kind == "team":
        return "team", team_from(config_id, load_team(config_id, version_id))
    return "agent", agent_from(config_id, load_version(config_id, version_id), tracked=True)


def plan_case(
    position: int,
    snapshot: dict[str, Any],
    config_id: UUID,
    kind: str,
    version_id: UUID,
    judge_unavailable: str | None = JUDGE_WITHOUT_MODEL,
    actor: str = "eval",
) -> PlannedCase:
    """`judge_unavailable` é o motivo de o juiz não rodar; None quando há juiz."""
    spec = EvalCaseInput.model_validate(snapshot)
    text, tools, judge = _split(spec)
    blocked = _blocked(spec)
    steps = _steps(spec)
    skipped: dict[str, str] = {}
    use_judge = judge is not None and judge_unavailable is None
    if judge is not None and judge_unavailable is not None:
        skipped["judge"] = judge_unavailable
    case_id = UUID(snapshot["id"]) if snapshot.get("id") else None
    wants_schema = _schema_check(spec) is not None
    nothing = not text and tools is None and not use_judge and blocked is None and steps is None
    if nothing and not wants_schema:
        # o Case do Agno recusa caso sem checagem; nada roda e o caso fica não avaliado
        return PlannedCase(position, case_id, spec.name, spec, None, skipped)
    field, runner = _runner_for(config_id, kind, version_id, actor)
    schema = getattr(runner, "output_schema", None) if wants_schema else None
    if wants_schema and not isinstance(schema, dict):
        skipped["schema"] = NO_SCHEMA
        schema = None
        if nothing:
            return PlannedCase(position, case_id, spec.name, spec, None, skipped)
    target = {field: runner}
    session_args = _context_args(runner, spec.context, actor)
    agno_case = Case(
        name=spec.name,
        input=spec.input,
        timeout_seconds=CASE_TIMEOUT_S,
        expected_tool_calls=tuple(tools.tools) if tools else None,
        allow_additional_tool_calls=tools.allow_additional if tools else True,
        scorer=AnsweredScorer()
        if blocked is not None
        else TextScorer(text, steps, schema)
        if text or steps is not None or schema is not None
        else None,
        criteria=judge.criteria if judge is not None and use_judge else None,
        judge_mode=JudgeMode(judge.mode) if judge is not None else JudgeMode.BINARY,
        judge_threshold=judge.threshold if judge is not None else 7,
        user_id=actor,
        **session_args,
        **target,
    )
    blocks = getattr(runner, "automata_blocks", None)
    return PlannedCase(position, case_id, spec.name, spec, agno_case, skipped, blocks)


def _context_args(runner: Any, context: list[str], actor: str) -> dict[str, Any]:
    """Sessão própria do caso, com os turnos anteriores rodados no `setup` do Case.

    O histórico sai do banco da sessão: o agente da suíte não passa pelo AgentFactory,
    que injetaria o banco, então ele entra aqui. Só a resposta a `input` é checada.
    """
    if not context:
        return {}
    runner.db = get_db()
    session_id = f"eval-{uuid4().hex}"

    async def setup() -> None:
        for message in context:
            await asyncio.wait_for(
                runner.arun(message, session_id=session_id, user_id=actor, stream=False),
                CONTEXT_TIMEOUT_S,
            )
        # bloqueio num turno anterior não é o do turno avaliado
        blocks = getattr(runner, "automata_blocks", None)
        if blocks is not None:
            blocks.blocks.clear()

    return {"session_id": session_id, "setup": setup}


def result_from(planned: PlannedCase, result: CaseResult | None) -> EvalResult:
    """Traduz o CaseResult do Agno para uma linha de eval_result."""
    text, tools, judge = _split(planned.spec)
    checks: list[dict[str, Any]] = []
    if text:
        detail = (result.score.detail or {}) if result and result.score else {}
        rules = detail.get("checks")
        checks.append(
            {
                "type": "text",
                # o scorer também confere as etapas no workflow: o texto passa pelas regras
                "passed": all(r["passed"] for r in rules) if rules else None,
                "rules": rules or [{"kind": c.kind, "value": c.value} for c in text],
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
    steps = _steps(planned.spec)
    if steps is not None:
        detail = (result.score.detail or {}) if result and result.score else {}
        verdict = detail.get("steps") or {}
        checks.append(
            {
                "type": "steps",
                "passed": verdict.get("passed") if verdict else None,
                "expected": steps.steps,
                "exclusive": steps.exclusive,
                "ran": verdict.get("ran", []),
                "missing": verdict.get("missing", []),
                "extra": verdict.get("extra", []),
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
    if _schema_check(planned.spec) is not None:
        detail = (result.score.detail or {}) if result and result.score else {}
        verdict = detail.get("schema") or {}
        checks.append(
            {
                "type": "schema",
                "passed": verdict.get("passed") if verdict else None,
                "errors": verdict.get("errors", []),
                "reason": planned.skipped.get("schema"),
            }
        )
    blocked = _blocked(planned.spec)
    if blocked is not None:
        return _blocked_result(planned, blocked, result)
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


def _blocked_result(
    planned: PlannedCase, check: BlockedCheck, result: CaseResult | None
) -> EvalResult:
    """O bloqueio chega ao Agno como run com erro; o veredito vem do registro de bloqueios."""
    last = planned.blocks.last if planned.blocks is not None else None
    rule = last.rule if last is not None and last.rule != RULE_BUDGET else None
    error: str | None = None
    if rule is not None:
        passed: bool | None = check.rule is None or rule == check.rule
        status = "passed" if passed else "failed"
    elif result is None or result.skipped:
        passed, status = None, "not_evaluated"
    elif result.timed_out or (result.error and result.score is None):
        # caiu sem bloquear e sem responder: falha da execução, não do guardrail
        passed, status = None, "error"
        error = "tempo esgotado" if result.timed_out and not result.error else result.error
    else:
        passed, status = False, "failed"
    return EvalResult(
        case_id=planned.case_id,
        case_name=planned.name,
        position=planned.position,
        status=status,
        checks=[{"type": "blocked", "passed": passed, "rule": check.rule, "blocked_by": rule}],
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


def _record_judge(
    run_id: UUID, config_id: UUID, actor: str, model_id: str, usage: JudgeUsage
) -> None:
    if not usage.total_tokens:
        return
    with Session(get_engine()) as session:
        UsageRepository(session).record_event(
            agent_config_id=config_id,
            user_id=actor,
            model_id=model_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost=cost_or_estimate(usage.cost, model_id, usage.input_tokens, usage.output_tokens),
            eval_run_id=run_id,
        )
        session.commit()


def _consumption(run_id: UUID) -> tuple[int, float | None]:
    """Casos e juiz: tudo que a execução gravou em usage_event."""
    with Session(get_engine()) as session:
        row = session.execute(
            select(
                func.coalesce(func.sum(UsageEvent.total_tokens), 0), func.sum(UsageEvent.cost)
            ).where(UsageEvent.eval_run_id == run_id)
        ).one()
        return int(row[0]), float(row[1]) if row[1] is not None else None


def _load(run_id: UUID) -> tuple[UUID, str, UUID, str, list[dict[str, Any]], str | None]:
    from app.models.config import AgentConfig

    with Session(get_engine()) as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            raise LookupError(f"eval_run {run_id} não existe")
        config = session.get(AgentConfig, run.agent_config_id)
        assert config is not None
        return (
            run.agent_config_id,
            config.kind,
            run.version_id,
            run.started_by,
            list(run.cases),
            run.judge_model,
        )


async def execute(run_id: UUID) -> None:
    """Roda a suíte em background; qualquer falha fora dos casos marca a execução como falha."""
    try:
        config_id, kind, version_id, actor, snapshots, judge_model = await asyncio.to_thread(
            _load, run_id
        )
        await asyncio.to_thread(_set, run_id, status="running", started_at=datetime.now(UTC))
        judge: Any = None
        usage = JudgeUsage()
        unavailable: str | None = None
        if models_map.demo_replay():
            unavailable = JUDGE_IN_DEMO
        elif judge_model is None:
            unavailable = JUDGE_WITHOUT_MODEL
        else:
            # sempre um modelo nosso: sem judge_model o Agno cairia num modelo da OpenAI
            judge, usage = metered(models_map.resolve_model(judge_model))
        planned = await asyncio.to_thread(
            lambda: [
                plan_case(i, snap, config_id, kind, version_id, unavailable, actor)
                for i, snap in enumerate(snapshots)
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
            await arun_cases(
                runnable,
                default_timeout=CASE_TIMEOUT_S,
                judge_model=judge,
                on_case_end=on_case_end,
            )
    except Exception as exc:
        logger.exception("suíte falhou", extra={"eval_run_id": str(run_id)})
        await asyncio.to_thread(
            _set, run_id, status="failed", error=str(exc), finished_at=datetime.now(UTC)
        )
        return
    finally:
        current_eval_run.reset(token)
        if judge_model is not None:
            await asyncio.to_thread(_record_judge, run_id, config_id, actor, judge_model, usage)

    total_tokens, cost = await asyncio.to_thread(_consumption, run_id)
    await asyncio.to_thread(
        _set,
        run_id,
        status="completed",
        total_tokens=total_tokens,
        cost=cost,
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
