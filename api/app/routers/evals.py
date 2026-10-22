"""Casos de teste e execução da suíte por agente e time (ADR-0015)."""

from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select

from app.authz import Scope, require_resource_scope, require_scopes
from app.db import SessionDep, get_db
from app.evals import webhook
from app.evals.compare import compare, suite_states
from app.evals.gate import draft_verdict, latest_run
from app.evals.runner import execute
from app.evals.scheduler import next_run, validate
from app.evals.service import EvalRunRefused, check_judge, create_run
from app.evals.suggest import suggest
from app.mcp.egress import EgressDenied
from app.models.config import AgentConfig
from app.models.eval import EvalCase, EvalResult, EvalRun, EvalSchedule
from app.models.run import AgentRun
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository, EvalRunRepository, EvalScheduleRepository
from app.schemas.eval import (
    MAX_CASES,
    CaseComparison,
    EvalCaseInput,
    EvalCaseResponse,
    EvalCaseSuggestion,
    EvalComparison,
    EvalResultResponse,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunSummary,
    EvalScheduleInput,
    EvalScheduleResponse,
    EvalSettings,
    EvalSettingsInput,
    EvalSuiteStatus,
    EvalTrigger,
    EvalVerdict,
    WebhookInput,
    WebhookIssued,
    WebhookTestResult,
    kind_problem,
)
from app.secrets import SecretsKeyMissing

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


def _fits(config: AgentConfig, body: EvalCaseInput) -> None:
    # tools e bloqueio são de cada etapa do workflow; etapas só existem nele (ADR-0022)
    problem = kind_problem(config.kind, body)
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)


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
            "context": case.context,
            "checks": case.checks,
            "source_run_id": case.source_run_id,
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


@router.get("/suggestion", response_model=EvalCaseSuggestion, dependencies=_WRITE)
def suggest_case(
    config_id: UUID, run_id: str, request: Request, session: SessionDep
) -> EvalCaseSuggestion:
    """Caso a partir de uma conversa real: o formulário abre preenchido e nada é gravado."""
    if _config_or_404(session, config_id).kind == "workflow":
        raise HTTPException(status_code=422, detail="Run de workflow ainda não vira caso")
    row = session.scalars(
        select(AgentRun).where(AgentRun.run_id == run_id, AgentRun.agent_config_id == config_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Run não encontrado neste agente")
    if row.eval_run_id is not None:
        raise HTTPException(status_code=422, detail="Run de teste não vira caso")
    if row.parent_run_id is not None:
        raise HTTPException(status_code=422, detail="Etapa de workflow não vira caso")
    if row.status == "blocked":
        raise HTTPException(status_code=422, detail="Run bloqueado por guardrail não vira caso")
    # a sugestão traz a conversa: mesma regra do trace, só o dono ou admin
    enforce = getattr(request.app.state, "enforce_scopes", False)
    is_admin = "agent_os:admin" in (getattr(request.state, "scopes", None) or [])
    if enforce and not is_admin and row.user_id != getattr(request.state, "user_id", None):
        raise HTTPException(status_code=403, detail="Só quem teve a conversa ou um admin")
    db = get_db()
    run = db.get_run(run_id)
    if run is None or isinstance(run, dict):
        raise HTTPException(status_code=404, detail="A conversa deste run não está mais guardada")
    previous = []
    if row.session_id:
        runs = db.get_runs(session_id=row.session_id, sort_by="created_at", sort_order="asc")
        previous = [
            r
            for r in (runs if isinstance(runs, list) else [])
            if r.run_id != run_id
            and not getattr(r, "parent_run_id", None)
            and (r.created_at or 0) <= (run.created_at or 0)
        ]
    found = suggest(run, previous)
    return EvalCaseSuggestion.model_validate(asdict(found))


@router.post("", response_model=EvalCaseResponse, status_code=201, dependencies=_WRITE)
def create_case(
    config_id: UUID, body: EvalCaseInput, request: Request, session: SessionDep
) -> EvalCaseResponse:
    _fits(_config_or_404(session, config_id), body)
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
            context=body.context,
            checks=[c.model_dump() for c in body.checks],
            source_run_id=body.source_run_id,
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
    _fits(_config_or_404(session, config_id), body)
    repo = EvalCaseRepository(session)
    case = _case_or_404(repo, config_id, case_id)
    if repo.name_taken(config_id, body.name, exclude=case_id):
        raise HTTPException(status_code=409, detail="Já existe um caso com esse nome")
    case.name = body.name
    case.input = body.input
    case.context = body.context
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


@runs_router.get("/compare", response_model=EvalComparison)
def compare_runs(config_id: UUID, base: UUID, target: UUID, session: SessionDep) -> EvalComparison:
    """Caso a caso entre duas execuções; tipicamente a vigente (base) e o rascunho (target)."""
    _config_or_404(session, config_id)
    repo = EvalRunRepository(session)
    before, after = repo.get(config_id, base), repo.get(config_id, target)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    cases = [CaseComparison.model_validate(asdict(c)) for c in compare(repo, before, after)]
    return EvalComparison(
        base=_summary(session, before),
        target=_summary(session, after),
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
        webhook_host=s.webhook_host,
        webhook_last_status=s.webhook_last_status,
        webhook_last_at=s.webhook_last_at,
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
    _config_or_404(session, config_id)
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


def _schedule_or_404(session: SessionDep, config_id: UUID) -> EvalSchedule:
    _config_or_404(session, config_id)
    schedule = EvalScheduleRepository(session).get(config_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Crie o agendamento antes do webhook")
    return schedule


@schedule_router.put("/webhook", response_model=WebhookIssued, dependencies=_WRITE)
def save_webhook(config_id: UUID, body: WebhookInput, session: SessionDep) -> WebhookIssued:
    """Cadastra ou troca o webhook; o segredo novo é devolvido uma vez só."""
    schedule = _schedule_or_404(session, config_id)
    try:
        encrypted, host, secret = webhook.seal(body.url)
    except (EgressDenied, SecretsKeyMissing) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    schedule.webhook_encrypted = encrypted
    schedule.webhook_host = host
    schedule.webhook_last_status = None
    schedule.webhook_last_at = None
    session.commit()
    return WebhookIssued(host=host, secret=secret)


@schedule_router.delete("/webhook", status_code=204, dependencies=_WRITE)
def delete_webhook(config_id: UUID, session: SessionDep) -> Response:
    schedule = _schedule_or_404(session, config_id)
    schedule.webhook_encrypted = None
    schedule.webhook_host = None
    schedule.webhook_last_status = None
    schedule.webhook_last_at = None
    session.commit()
    return Response(status_code=204)


@schedule_router.post("/webhook/test", response_model=WebhookTestResult, dependencies=_WRITE)
def test_webhook(config_id: UUID, session: SessionDep) -> WebhookTestResult:
    """Manda um suite.test, uma tentativa só, para conferir a integração."""
    schedule = _schedule_or_404(session, config_id)
    if schedule.webhook_encrypted is None:
        raise HTTPException(status_code=404, detail="Agendamento sem webhook")
    config = _config_or_404(session, config_id)
    try:
        target = webhook.unseal(schedule.webhook_encrypted)
    except SecretsKeyMissing as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    body = webhook.body_for(
        "suite.test",
        {"config_id": str(config_id), "config_name": config.name},
        f"Teste do aviso da suíte de {config.name}: o webhook está funcionando.",
    )
    status = webhook.deliver(target, "suite.test", body, attempts=1)
    schedule.webhook_last_status = status
    schedule.webhook_last_at = datetime.now(UTC)
    session.commit()
    return WebhookTestResult(status=status, delivered=status.startswith("HTTP 2"))


status_router = APIRouter(
    prefix="/api/v1/eval-status",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)


@status_router.get("", response_model=list[EvalSuiteStatus])
def list_suite_status(session: SessionDep) -> list[EvalSuiteStatus]:
    """Estado da suíte de cada config que já rodou: para a lista de agentes e times."""
    return [
        EvalSuiteStatus(
            config_id=st.config_id,
            state=st.state,
            last_run=_summary(session, st.last_run),
            previous_run_id=st.previous_run_id,
            regressions=st.regressions,
        )
        for st in suite_states(session)
    ]
