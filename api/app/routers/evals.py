"""Casos de teste e execução da suíte por agente e time (ADR-0015)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from app.authz import Scope, require_resource_scope, require_scopes
from app.db import SessionDep
from app.evals.gate import draft_verdict, latest_run
from app.evals.runner import execute
from app.evals.scheduler import next_run, validate
from app.evals.service import EvalRunRefused, check_judge, create_run
from app.models.config import AgentConfig
from app.models.eval import EvalCase, EvalResult, EvalRun, EvalSchedule
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository, EvalRunRepository, EvalScheduleRepository
from app.schemas.eval import (
    MAX_CASES,
    CaseComparison,
    EvalCaseInput,
    EvalCaseResponse,
    EvalComparison,
    EvalResultResponse,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunSummary,
    EvalScheduleInput,
    EvalScheduleResponse,
    EvalSettings,
    EvalSettingsInput,
    EvalTrigger,
    EvalVerdict,
)

router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-cases",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)

_WRITE = [Depends(require_scopes(Scope.EVALS_WRITE))]


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


def _trigger(actor: str) -> EvalTrigger:
    # o sub dos tokens de integração é "integration:<id>" (routers/integrations.py)
    return "integration" if actor.startswith("integration:") else "manual"


def _config_or_404(session: SessionDep, config_id: UUID) -> AgentConfig:
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    return config


def _testable(config: AgentConfig) -> None:
    # o runner de suíte do Agno roda agente ou time; workflow fica para depois
    if config.kind == "workflow":
        raise HTTPException(status_code=422, detail="Workflow ainda não tem suíte de testes")


def _case_or_404(repo: EvalCaseRepository, config_id: UUID, case_id: UUID) -> EvalCase:
    case = repo.get(config_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return case


def to_response(case: EvalCase) -> EvalCaseResponse:
    return EvalCaseResponse.model_validate(
        {
            "id": case.id,
            "agent_config_id": case.agent_config_id,
            "name": case.name,
            "input": case.input,
            "checks": case.checks,
            "position": case.position,
            "updated_by": case.updated_by,
            "created_at": case.created_at,
            "updated_at": case.updated_at,
        }
    )


@router.get("", response_model=list[EvalCaseResponse])
def list_cases(config_id: UUID, session: SessionDep) -> list[EvalCaseResponse]:
    _config_or_404(session, config_id)
    return [to_response(c) for c in EvalCaseRepository(session).list_by_config(config_id)]


@router.post("", response_model=EvalCaseResponse, status_code=201, dependencies=_WRITE)
def create_case(
    config_id: UUID, body: EvalCaseInput, request: Request, session: SessionDep
) -> EvalCaseResponse:
    _testable(_config_or_404(session, config_id))
    repo = EvalCaseRepository(session)
    if repo.count(config_id) >= MAX_CASES:
        raise HTTPException(status_code=422, detail=f"No máximo {MAX_CASES} casos por suíte")
    if repo.name_taken(config_id, body.name):
        raise HTTPException(status_code=409, detail="Já existe um caso com esse nome")
    case = repo.add(
        EvalCase(
            agent_config_id=config_id,
            name=body.name,
            input=body.input,
            checks=[c.model_dump() for c in body.checks],
            position=repo.next_position(config_id),
            updated_by=_actor(request),
        )
    )
    session.commit()
    session.refresh(case)
    return to_response(case)


@router.put("/{case_id}", response_model=EvalCaseResponse, dependencies=_WRITE)
def update_case(
    config_id: UUID, case_id: UUID, body: EvalCaseInput, request: Request, session: SessionDep
) -> EvalCaseResponse:
    _config_or_404(session, config_id)
    repo = EvalCaseRepository(session)
    case = _case_or_404(repo, config_id, case_id)
    if repo.name_taken(config_id, body.name, exclude=case_id):
        raise HTTPException(status_code=409, detail="Já existe um caso com esse nome")
    case.name = body.name
    case.input = body.input
    case.checks = [c.model_dump() for c in body.checks]
    case.updated_by = _actor(request)
    session.commit()
    session.refresh(case)
    return to_response(case)


@router.delete("/{case_id}", status_code=204, dependencies=_WRITE)
def delete_case(config_id: UUID, case_id: UUID, session: SessionDep) -> Response:
    _config_or_404(session, config_id)
    repo = EvalCaseRepository(session)
    repo.delete(_case_or_404(repo, config_id, case_id))
    session.commit()
    return Response(status_code=204)


runs_router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-runs",
    tags=["evals"],
    # aceita também o escopo por config dos tokens de integração (ADR-0016)
    dependencies=[Depends(require_resource_scope("evals", "read"))],
)


def verdict(run: EvalRun) -> EvalVerdict:
    if run.status in ("queued", "running"):
        return "pending"
    # mesma regra do gate: não avaliado não conta como aprovado
    ok = run.status == "completed" and run.total > 0 and run.passed == run.total
    return "passed" if ok else "failed"


def _summary(session: SessionDep, run: EvalRun) -> EvalRunSummary:
    version = ConfigRepository(session).get_version(run.version_id)
    assert version is not None
    return EvalRunSummary(
        id=run.id,
        agent_config_id=run.agent_config_id,
        version_id=run.version_id,
        version_number=version.version_number,
        version_status=version.status.value,
        status=run.status,
        total=run.total,
        passed=run.passed,
        failed=run.failed,
        not_evaluated=run.not_evaluated,
        error=run.error,
        judge_model=run.judge_model,
        total_tokens=run.total_tokens,
        cost=float(run.cost) if run.cost is not None else None,
        started_by=run.started_by,
        trigger=run.trigger,
        target=run.target,
        verdict=verdict(run),
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _result(r: EvalResult) -> EvalResultResponse:
    return EvalResultResponse(
        id=r.id,
        case_id=r.case_id,
        case_name=r.case_name,
        position=r.position,
        status=r.status,
        checks=r.checks,
        output=r.output,
        tools_called=r.tools_called,
        duration_ms=r.duration_ms,
        error=r.error,
        session_id=r.session_id,
    )


@runs_router.post(
    "",
    response_model=EvalRunSummary,
    status_code=202,
    dependencies=[Depends(require_resource_scope("evals", "run"))],
)
def start_run(
    config_id: UUID,
    body: EvalRunCreate,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
) -> EvalRunSummary:
    config = _config_or_404(session, config_id)
    try:
        actor = _actor(request)
        run = create_run(session, config, body, actor=actor, trigger=_trigger(actor))
    except EvalRunRefused as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    background.add_task(execute, run.id)
    return _summary(session, run)


@runs_router.get("", response_model=list[EvalRunSummary])
def list_runs(config_id: UUID, session: SessionDep) -> list[EvalRunSummary]:
    _config_or_404(session, config_id)
    return [_summary(session, r) for r in EvalRunRepository(session).list_by_config(config_id)]


def _change(base: str | None, target: str | None) -> str:
    if base is None:
        return "new"
    if target is None:
        return "removed"
    if base == "passed" and target != "passed":
        return "regression"
    if base != "passed" and target == "passed":
        return "fix"
    return "same"


@runs_router.get("/compare", response_model=EvalComparison)
def compare_runs(config_id: UUID, base: UUID, target: UUID, session: SessionDep) -> EvalComparison:
    """Caso a caso entre duas execuções; tipicamente a vigente (base) e o rascunho (target)."""
    _config_or_404(session, config_id)
    repo = EvalRunRepository(session)
    runs = {
        key: repo.get(config_id, run_id) for key, run_id in (("base", base), ("target", target))
    }
    if runs["base"] is None or runs["target"] is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")

    def keyed(run: EvalRun) -> dict[str, EvalResult]:
        # pelo id do caso; caso apagado depois da execução cai para o nome
        return {str(r.case_id or r.case_name): r for r in repo.results(run.id)}

    before, after = keyed(runs["base"]), keyed(runs["target"])
    order = list(after) + [k for k in before if k not in after]
    cases = []
    for key in order:
        b, a = before.get(key), after.get(key)
        ref = a or b
        assert ref is not None
        cases.append(
            CaseComparison.model_validate(
                {
                    "case_id": ref.case_id,
                    "case_name": ref.case_name,
                    "base_status": b.status if b else None,
                    "target_status": a.status if a else None,
                    "change": _change(b.status if b else None, a.status if a else None),
                }
            )
        )
    return EvalComparison(
        base=_summary(session, runs["base"]),
        target=_summary(session, runs["target"]),
        cases=cases,
        regressions=sum(1 for c in cases if c.change == "regression"),
        fixes=sum(1 for c in cases if c.change == "fix"),
    )


@runs_router.get("/{run_id}", response_model=EvalRunDetail)
def get_run(config_id: UUID, run_id: UUID, session: SessionDep) -> EvalRunDetail:
    _config_or_404(session, config_id)
    repo = EvalRunRepository(session)
    run = repo.get(config_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    summary = _summary(session, run)
    return EvalRunDetail(**summary.model_dump(), results=[_result(r) for r in repo.results(run.id)])


settings_router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-settings",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)


def _settings(session: SessionDep, config: AgentConfig) -> EvalSettings:
    run = latest_run(session, config)
    verdict = draft_verdict(session, config)
    return EvalSettings(
        require_passing_evals=config.require_passing_evals,
        draft_version_id=config.draft_version_id,
        draft_run=_summary(session, run) if run else None,
        can_publish=verdict.ok or not config.require_passing_evals,
        reason=verdict.reason,
    )


@settings_router.get("", response_model=EvalSettings)
def read_eval_settings(config_id: UUID, session: SessionDep) -> EvalSettings:
    return _settings(session, _config_or_404(session, config_id))


@settings_router.put("", response_model=EvalSettings, dependencies=_WRITE)
def update_settings(config_id: UUID, body: EvalSettingsInput, session: SessionDep) -> EvalSettings:
    config = _config_or_404(session, config_id)
    _testable(config)
    config.require_passing_evals = body.require_passing_evals
    session.commit()
    session.refresh(config)
    return _settings(session, config)


schedule_router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-schedule",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)


def _schedule(s: EvalSchedule) -> EvalScheduleResponse:
    return EvalScheduleResponse(
        agent_config_id=s.agent_config_id,
        cron_expr=s.cron_expr,
        timezone=s.timezone,
        target=s.target,
        judge_model=s.judge_model,
        enabled=s.enabled,
        next_run_at=s.next_run_at,
        last_attempt_at=s.last_attempt_at,
        last_run_id=s.last_run_id,
        last_error=s.last_error,
        updated_by=s.updated_by,
        updated_at=s.updated_at,
    )


@schedule_router.get("", response_model=EvalScheduleResponse)
def read_schedule(config_id: UUID, session: SessionDep) -> EvalScheduleResponse:
    _config_or_404(session, config_id)
    schedule = EvalScheduleRepository(session).get(config_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Suíte sem agendamento")
    return _schedule(schedule)


@schedule_router.put("", response_model=EvalScheduleResponse, dependencies=_WRITE)
def save_schedule(
    config_id: UUID, body: EvalScheduleInput, request: Request, session: SessionDep
) -> EvalScheduleResponse:
    config = _config_or_404(session, config_id)
    _testable(config)
    reason = validate(body.cron_expr, body.timezone)
    if reason is not None:
        raise HTTPException(status_code=422, detail=reason)
    try:
        # recusa já na gravação o que o horário recusaria: juiz sem modelo, modelo sem schema
        check_judge(EvalCaseRepository(session).list_by_config(config_id), body.judge_model)
    except EvalRunRefused as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    repo = EvalScheduleRepository(session)
    schedule = repo.get(config_id) or repo.add(
        EvalSchedule(
            agent_config_id=config_id,
            cron_expr=body.cron_expr,
            timezone=body.timezone,
            updated_by=_actor(request),
        )
    )
    schedule.cron_expr = body.cron_expr
    schedule.timezone = body.timezone
    schedule.target = body.target
    schedule.judge_model = body.judge_model
    schedule.enabled = body.enabled
    schedule.updated_by = _actor(request)
    schedule.next_run_at = (
        next_run(body.cron_expr, body.timezone, datetime.now(UTC)) if body.enabled else None
    )
    session.commit()
    session.refresh(schedule)
    return _schedule(schedule)


@schedule_router.delete("", status_code=204, dependencies=_WRITE)
def delete_schedule(config_id: UUID, session: SessionDep) -> Response:
    _config_or_404(session, config_id)
    repo = EvalScheduleRepository(session)
    schedule = repo.get(config_id)
    if schedule is not None:
        repo.delete(schedule)
        session.commit()
    return Response(status_code=204)
