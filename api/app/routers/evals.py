"""Casos de teste e execução da suíte por agente e time (ADR-0015)."""

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.authz import Scope, require_resource_scope, require_scopes, scopes_enforced
from app.db import SessionDep, get_db
from app.evals import csv_cases, webhook
from app.evals.compare import compare, suite_states
from app.evals.gate import draft_verdict, latest_run
from app.evals.runner import execute
from app.evals.scheduler import next_run, validate
from app.evals.service import EvalRunRefused, check_judge, create_run
from app.evals.suggest import suggest
from app.guardrails.instance import effective
from app.guardrails.instance import floor as instance_floor
from app.guardrails.pii import CustomPattern
from app.mcp.egress import EgressDenied
from app.models.config import AgentConfig, AgentConfigVersion
from app.models.eval import EvalCase, EvalResult, EvalRun, EvalSchedule
from app.models.run import AgentRun
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository, EvalRunRepository, EvalScheduleRepository
from app.schemas.config import ConfigPayload
from app.schemas.eval import (
    MAX_BATCH_SUGGESTIONS,
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
from app.schemas.workflow import walk
from app.secrets import SecretsKeyMissing

router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-cases",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)

_WRITE = [Depends(require_scopes(Scope.EVALS_WRITE))]


def _actor(request: Request) -> str:
    """Quem fez a ação; "panel" quando a requisição não traz usuário."""
    return str(getattr(request.state, "user_id", None) or "panel")


def _trigger(actor: str) -> EvalTrigger:
    """Origem da execução: token de integração ou alguém no painel."""
    # o sub dos tokens de integração é "integration:<id>" (routers/integrations.py)
    return "integration" if actor.startswith("integration:") else "manual"


def _config_or_404(session: SessionDep, config_id: UUID) -> AgentConfig:
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    return config


def _workflow_shape(session: Any, config: AgentConfig) -> tuple[int, set[str] | None]:
    """Histórico e etapas do rascunho, ou da versão vigente, do workflow (ADR-0038)."""
    if config.kind != "workflow":
        return 0, None
    version_id = config.draft_version_id or config.current_version_id
    version = session.get(AgentConfigVersion, version_id) if version_id else None
    if version is None:
        return 0, None
    workflow = ConfigPayload.model_validate(version.payload).workflow
    if workflow is None:
        return 0, None
    step_names = {step.name for step, _ in walk(workflow.steps)}
    return workflow.history_runs, step_names


def _fits(config: AgentConfig, body: EvalCaseInput, session: Any = None) -> None:
    """Recusa com 422 checagem que não faz sentido para o tipo do config."""
    # tools e bloqueio são de cada etapa do workflow; etapas só existem nele (ADR-0022)
    history_runs, step_names = (
        _workflow_shape(session, config) if session is not None else (0, None)
    )
    problem = kind_problem(config.kind, body, history_runs, step_names)
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)


def _case_or_404(repo: EvalCaseRepository, config_id: UUID, case_id: UUID) -> EvalCase:
    case = repo.get(config_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Caso não encontrado")
    return case


def to_response(case: EvalCase) -> EvalCaseResponse:
    """Caso gravado no formato da resposta."""
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
    return [to_response(case) for case in EvalCaseRepository(session).list_by_config(config_id)]


@router.get("/suggestion", response_model=EvalCaseSuggestion, dependencies=_WRITE)
def suggest_case(
    config_id: UUID, run_id: str, request: Request, session: SessionDep
) -> EvalCaseSuggestion:
    """Caso a partir de uma conversa real: o formulário abre preenchido e nada é gravado."""
    if _config_or_404(session, config_id).kind == "workflow":
        raise HTTPException(status_code=422, detail="Run de workflow ainda não vira caso")
    agent_run = session.scalars(
        select(AgentRun).where(AgentRun.run_id == run_id, AgentRun.agent_config_id == config_id)
    ).first()
    if agent_run is None:
        raise HTTPException(status_code=404, detail="Run não encontrado neste agente")
    if agent_run.eval_run_id is not None:
        raise HTTPException(status_code=422, detail="Run de teste não vira caso")
    if agent_run.parent_run_id is not None:
        raise HTTPException(status_code=422, detail="Etapa de workflow não vira caso")
    if agent_run.status == "blocked":
        raise HTTPException(status_code=422, detail="Run bloqueado por guardrail não vira caso")
    # a sugestão traz a conversa: mesma regra do trace, só o dono ou admin
    enforce = scopes_enforced(request)
    is_admin = "agent_os:admin" in (getattr(request.state, "scopes", None) or [])
    if enforce and not is_admin and agent_run.user_id != getattr(request.state, "user_id", None):
        raise HTTPException(status_code=403, detail="Só quem teve a conversa ou um admin")
    suggestion = _suggestion_from(
        get_db(), agent_run, _custom_pii(session, agent_run.agent_config_id)
    )
    if suggestion is None:
        raise HTTPException(status_code=404, detail="A conversa deste run não está mais guardada")
    return suggestion


def _custom_pii(session: Session, config_id: UUID) -> tuple[CustomPattern, ...]:
    """Padrões próprios de dado pessoal do agente e do piso, para a máscara da sugestão."""
    config_repo = ConfigRepository(session)
    config = config_repo.get_config(config_id)
    version_id = config.current_version_id or config.draft_version_id if config else None
    version = config_repo.get_version(version_id) if version_id else None
    if version is None:
        return ()
    own = ConfigPayload.model_validate(version.payload).guardrails
    return effective(instance_floor(), own).pii.custom_patterns()


def _suggestion_from(
    db: Any, agent_run: AgentRun, custom_patterns: tuple[CustomPattern, ...] = ()
) -> EvalCaseSuggestion | None:
    """Sugestão a partir do run guardado no Agno; None quando a conversa não existe mais."""
    stored_run = db.get_run(agent_run.run_id)
    if stored_run is None or isinstance(stored_run, dict):
        return None
    # turnos anteriores da mesma sessão viram o contexto do caso; etapas de workflow e
    # turnos depois do run escolhido ficam de fora
    previous_runs = []
    if agent_run.session_id:
        session_runs = db.get_runs(
            session_id=agent_run.session_id, sort_by="created_at", sort_order="asc"
        )
        previous_runs = [
            earlier_run
            for earlier_run in (session_runs if isinstance(session_runs, list) else [])
            if earlier_run.run_id != agent_run.run_id
            and not getattr(earlier_run, "parent_run_id", None)
            and (earlier_run.created_at or 0) <= (stored_run.created_at or 0)
        ]
    return EvalCaseSuggestion.model_validate(
        asdict(suggest(stored_run, previous_runs, custom_patterns))
    )


@router.get("/suggestions", response_model=list[EvalCaseSuggestion], dependencies=_WRITE)
def suggest_cases(
    config_id: UUID,
    request: Request,
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=MAX_BATCH_SUGGESTIONS),
) -> list[EvalCaseSuggestion]:
    """Sugestões em lote das conversas recentes (ADR-0038); nada é gravado."""
    if _config_or_404(session, config_id).kind == "workflow":
        raise HTTPException(status_code=422, detail="Run de workflow ainda não vira caso")
    used_run_ids = {
        case.source_run_id
        for case in EvalCaseRepository(session).list_by_config(config_id)
        if case.source_run_id
    }
    query = (
        select(AgentRun)
        .where(
            AgentRun.agent_config_id == config_id,
            AgentRun.status == "success",
            AgentRun.eval_run_id.is_(None),
            AgentRun.parent_run_id.is_(None),
        )
        .order_by(AgentRun.created_at.desc())
    )
    # a sugestão traz a conversa: quem não é admin vê só as próprias
    enforce = scopes_enforced(request)
    is_admin = "agent_os:admin" in (getattr(request.state, "scopes", None) or [])
    if enforce and not is_admin:
        query = query.where(AgentRun.user_id == getattr(request.state, "user_id", None))
    db = get_db()
    custom_patterns = _custom_pii(session, config_id)
    suggestions: list[EvalCaseSuggestion] = []
    # olha um lote maior: conversa já usada ou apagada do Agno fica de fora
    for agent_run in session.scalars(query.limit(limit * 3)):
        if agent_run.run_id in used_run_ids:
            continue
        suggestion = _suggestion_from(db, agent_run, custom_patterns)
        if suggestion is not None:
            suggestions.append(suggestion)
        if len(suggestions) >= limit:
            break
    return suggestions


class CaseImportRow(BaseModel):
    line: int
    name: str
    errors: list[str]


class CaseImportReport(BaseModel):
    created: int
    dry_run: bool
    rows: list[CaseImportRow]


@router.get("/export", response_class=Response)
def export_cases(config_id: UUID, session: SessionDep) -> Response:
    """Suíte em CSV (ADR-0043), no formato que a importação lê."""
    config = _config_or_404(session, config_id)
    body = csv_cases.dump(EvalCaseRepository(session).list_by_config(config_id))
    filename = re.sub(r"[^A-Za-z0-9_-]+", "-", config.name).strip("-") or "suite"
    return Response(
        content=body.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="casos-{filename}.csv"'},
    )


@router.post("/import", response_model=CaseImportReport, dependencies=_WRITE)
def import_cases(
    config_id: UUID,
    request: Request,
    session: SessionDep,
    file: UploadFile,
    dry_run: bool = Query(default=False),
) -> CaseImportReport | JSONResponse:
    """Tudo ou nada: com qualquer linha errada nada é gravado (ADR-0043).

    Síncrona: o banco é síncrono e rodava no event loop, travando a API num arquivo
    grande (Fase 49). O FastAPI leva a rota para o threadpool."""
    config = _config_or_404(session, config_id)
    # um byte além do teto basta para o parse recusar o arquivo grande demais
    raw_csv = file.file.read(csv_cases.MAX_BYTES + 1)
    try:
        rows = csv_cases.parse(raw_csv)
    except csv_cases.CsvError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="Nenhum caso no arquivo")
    case_repo = EvalCaseRepository(session)
    existing = case_repo.list_by_config(config_id)
    # o limite antes de olhar cada linha: 100 mil linhas não viram 100 mil consultas
    free_slots = MAX_CASES - len(existing)
    if len(rows) > free_slots:
        raise HTTPException(
            status_code=422,
            detail=f"A suíte comporta mais {max(free_slots, 0)} casos; o arquivo tem {len(rows)}",
        )
    history_runs, step_names = _workflow_shape(session, config)
    existing_names = {case.name.casefold() for case in existing}
    # nome de caso é único sem diferença de caixa, no arquivo e contra a suíte atual
    names_in_file: set[str] = set()
    for row in rows:
        if row.case is not None:
            problem = kind_problem(config.kind, row.case, history_runs, step_names)
            if problem is not None:
                row.errors.append(problem)
        folded_name = row.name.casefold()
        if row.name and folded_name in names_in_file:
            row.errors.append("nome repetido no arquivo")
        elif row.name and folded_name in existing_names:
            row.errors.append("já existe um caso com esse nome na suíte")
        names_in_file.add(folded_name)
    report = CaseImportReport(
        created=0,
        dry_run=dry_run,
        rows=[CaseImportRow(line=row.line, name=row.name, errors=row.errors) for row in rows],
    )
    if dry_run:
        return report
    if any(row.errors for row in rows):
        return JSONResponse(status_code=422, content=report.model_dump())
    actor = _actor(request)
    for row in rows:
        assert row.case is not None
        case_repo.add(
            EvalCase(
                agent_config_id=config_id,
                name=row.case.name,
                input=row.case.input,
                context=row.case.context,
                checks=[check.model_dump() for check in row.case.checks],
                position=case_repo.next_position(config_id),
                updated_by=actor,
            )
        )
    session.commit()
    report.created = len(rows)
    return report


@router.post("", response_model=EvalCaseResponse, status_code=201, dependencies=_WRITE)
def create_case(
    config_id: UUID, body: EvalCaseInput, request: Request, session: SessionDep
) -> EvalCaseResponse:
    """Cria o caso no fim da suíte, respeitando o teto de casos e o nome único."""
    _fits(_config_or_404(session, config_id), body, session)
    case_repo = EvalCaseRepository(session)
    if case_repo.count(config_id) >= MAX_CASES:
        raise HTTPException(status_code=422, detail=f"No máximo {MAX_CASES} casos por suíte")
    if case_repo.name_taken(config_id, body.name):
        raise HTTPException(status_code=409, detail="Já existe um caso com esse nome")
    case = case_repo.add(
        EvalCase(
            agent_config_id=config_id,
            name=body.name,
            input=body.input,
            context=body.context,
            checks=[check.model_dump() for check in body.checks],
            source_run_id=body.source_run_id,
            position=case_repo.next_position(config_id),
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
    _fits(_config_or_404(session, config_id), body, session)
    case_repo = EvalCaseRepository(session)
    case = _case_or_404(case_repo, config_id, case_id)
    if case_repo.name_taken(config_id, body.name, exclude=case_id):
        raise HTTPException(status_code=409, detail="Já existe um caso com esse nome")
    case.name = body.name
    case.input = body.input
    case.context = body.context
    case.checks = [check.model_dump() for check in body.checks]
    case.updated_by = _actor(request)
    session.commit()
    session.refresh(case)
    return to_response(case)


@router.delete("/{case_id}", status_code=204, dependencies=_WRITE)
def delete_case(config_id: UUID, case_id: UUID, session: SessionDep) -> Response:
    _config_or_404(session, config_id)
    case_repo = EvalCaseRepository(session)
    case_repo.delete(_case_or_404(case_repo, config_id, case_id))
    session.commit()
    return Response(status_code=204)


runs_router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-runs",
    tags=["evals"],
    # aceita também o escopo por config dos tokens de integração (ADR-0016)
    dependencies=[Depends(require_resource_scope("evals", "read"))],
)


def verdict(run: EvalRun) -> EvalVerdict:
    """Resultado da execução para o painel e as integrações: pendente, aprovada ou reprovada."""
    if run.status in ("queued", "running"):
        return "pending"
    # mesma regra do gate: não avaliado não conta como aprovado
    all_passed = run.status == "completed" and run.total > 0 and run.passed == run.total
    return "passed" if all_passed else "failed"


def _summary(session: SessionDep, run: EvalRun) -> EvalRunSummary:
    """Resumo da execução com o número e o status da versão testada."""
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


def _result(result: EvalResult) -> EvalResultResponse:
    return EvalResultResponse(
        id=result.id,
        case_id=result.case_id,
        case_name=result.case_name,
        position=result.position,
        status=result.status,
        checks=result.checks,
        output=result.output,
        tools_called=result.tools_called,
        duration_ms=result.duration_ms,
        error=result.error,
        session_id=result.session_id,
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
    """Enfileira a execução da suíte e responde 202; os casos rodam em background."""
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
    return [
        _summary(session, eval_run)
        for eval_run in EvalRunRepository(session).list_by_config(config_id)
    ]


@runs_router.get("/compare", response_model=EvalComparison)
def compare_runs(config_id: UUID, base: UUID, target: UUID, session: SessionDep) -> EvalComparison:
    """Caso a caso entre duas execuções; tipicamente a vigente (base) e o rascunho (target)."""
    _config_or_404(session, config_id)
    run_repo = EvalRunRepository(session)
    before, after = run_repo.get(config_id, base), run_repo.get(config_id, target)
    if before is None or after is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    cases = [
        CaseComparison.model_validate(asdict(comparison))
        for comparison in compare(run_repo, before, after)
    ]
    return EvalComparison(
        base=_summary(session, before),
        target=_summary(session, after),
        cases=cases,
        regressions=sum(1 for case in cases if case.change == "regression"),
        fixes=sum(1 for case in cases if case.change == "fix"),
    )


@runs_router.get("/{run_id}", response_model=EvalRunDetail)
def get_run(config_id: UUID, run_id: UUID, session: SessionDep) -> EvalRunDetail:
    _config_or_404(session, config_id)
    run_repo = EvalRunRepository(session)
    run = run_repo.get(config_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    summary = _summary(session, run)
    return EvalRunDetail(
        **summary.model_dump(), results=[_result(result) for result in run_repo.results(run.id)]
    )


settings_router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-settings",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)


def _settings(session: SessionDep, config: AgentConfig) -> EvalSettings:
    """Gate de publicação do config e se o rascunho atual passaria por ele."""
    draft_run = latest_run(session, config)
    publish_check = draft_verdict(session, config)
    return EvalSettings(
        require_passing_evals=config.require_passing_evals,
        draft_version_id=config.draft_version_id,
        draft_run=_summary(session, draft_run) if draft_run else None,
        can_publish=publish_check.ok or not config.require_passing_evals,
        reason=publish_check.reason,
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


def _schedule(schedule: EvalSchedule) -> EvalScheduleResponse:
    return EvalScheduleResponse(
        agent_config_id=schedule.agent_config_id,
        cron_expr=schedule.cron_expr,
        timezone=schedule.timezone,
        target=schedule.target,
        judge_model=schedule.judge_model,
        enabled=schedule.enabled,
        next_run_at=schedule.next_run_at,
        last_attempt_at=schedule.last_attempt_at,
        last_run_id=schedule.last_run_id,
        last_error=schedule.last_error,
        webhook_host=schedule.webhook_host,
        webhook_last_status=schedule.webhook_last_status,
        webhook_last_at=schedule.webhook_last_at,
        updated_by=schedule.updated_by,
        updated_at=schedule.updated_at,
    )


@schedule_router.get("", response_model=EvalScheduleResponse | None)
def read_schedule(config_id: UUID, session: SessionDep) -> EvalScheduleResponse | None:
    """`null` quando a suíte não tem agendamento: é o estado normal, não um erro."""
    _config_or_404(session, config_id)
    schedule = EvalScheduleRepository(session).get(config_id)
    return _schedule(schedule) if schedule is not None else None


@schedule_router.put("", response_model=EvalScheduleResponse, dependencies=_WRITE)
def save_schedule(
    config_id: UUID, body: EvalScheduleInput, request: Request, session: SessionDep
) -> EvalScheduleResponse:
    """Cria ou troca o agendamento da suíte e calcula o próximo horário."""
    _config_or_404(session, config_id)
    reason = validate(body.cron_expr, body.timezone)
    if reason is not None:
        raise HTTPException(status_code=422, detail=reason)
    try:
        # recusa já na gravação o que o horário recusaria: juiz sem modelo, modelo sem schema
        check_judge(EvalCaseRepository(session).list_by_config(config_id), body.judge_model)
    except EvalRunRefused as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    schedule_repo = EvalScheduleRepository(session)
    schedule = schedule_repo.get(config_id) or schedule_repo.add(
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
    schedule_repo = EvalScheduleRepository(session)
    schedule = schedule_repo.get(config_id)
    if schedule is not None:
        schedule_repo.delete(schedule)
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
    """Tira o webhook do agendamento; o agendamento continua."""
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
    delivery_status = webhook.deliver(target, "suite.test", body, attempts=1)
    schedule.webhook_last_status = delivery_status
    schedule.webhook_last_at = datetime.now(UTC)
    session.commit()
    return WebhookTestResult(status=delivery_status, delivered=delivery_status.startswith("HTTP 2"))


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
            config_id=suite_state.config_id,
            state=suite_state.state,
            last_run=_summary(session, suite_state.last_run),
            previous_run_id=suite_state.previous_run_id,
            regressions=suite_state.regressions,
        )
        for suite_state in suite_states(session)
    ]
