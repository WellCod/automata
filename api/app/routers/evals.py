"""Casos de teste e execução da suíte por agente e time (ADR-0015)."""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.evals.runner import execute
from app.models.config import AgentConfig
from app.models.eval import EvalCase, EvalResult, EvalRun
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository, EvalRunRepository
from app.schemas.eval import (
    MAX_CASES,
    EvalCaseInput,
    EvalCaseResponse,
    EvalResultResponse,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunSummary,
)

router = APIRouter(
    prefix="/api/v1/configs/{config_id}/eval-cases",
    tags=["evals"],
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)

_WRITE = [Depends(require_scopes(Scope.EVALS_WRITE))]


def _actor(request: Request) -> str:
    return str(getattr(request.state, "user_id", None) or "panel")


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
    dependencies=[Depends(require_scopes(Scope.EVALS_READ))],
)


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
        started_by=run.started_by,
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
    dependencies=[Depends(require_scopes(Scope.EVALS_RUN))],
)
def start_run(
    config_id: UUID,
    body: EvalRunCreate,
    request: Request,
    background: BackgroundTasks,
    session: SessionDep,
) -> EvalRunSummary:
    config = _config_or_404(session, config_id)
    _testable(config)
    version_id = body.version_id or config.draft_version_id or config.current_version_id
    if version_id is None:
        raise HTTPException(status_code=422, detail="Config sem versão para testar")
    version = ConfigRepository(session).get_version(version_id)
    if version is None or version.config_id != config_id:
        raise HTTPException(status_code=422, detail="Versão não é desta config")
    cases = EvalCaseRepository(session).list_by_config(config_id)
    if not cases:
        raise HTTPException(status_code=422, detail="Suíte sem casos")
    runs = EvalRunRepository(session)
    if runs.active(config_id) is not None:
        raise HTTPException(status_code=409, detail="Já há uma execução em andamento")
    run = runs.add(
        EvalRun(
            agent_config_id=config_id,
            version_id=version_id,
            status="queued",
            total=len(cases),
            cases=[
                {"id": str(c.id), "name": c.name, "input": c.input, "checks": c.checks}
                for c in cases
            ],
            started_by=_actor(request),
        )
    )
    session.commit()
    session.refresh(run)
    background.add_task(execute, run.id)
    return _summary(session, run)


@runs_router.get("", response_model=list[EvalRunSummary])
def list_runs(config_id: UUID, session: SessionDep) -> list[EvalRunSummary]:
    _config_or_404(session, config_id)
    return [_summary(session, r) for r in EvalRunRepository(session).list_by_config(config_id)]


@runs_router.get("/{run_id}", response_model=EvalRunDetail)
def get_run(config_id: UUID, run_id: UUID, session: SessionDep) -> EvalRunDetail:
    _config_or_404(session, config_id)
    repo = EvalRunRepository(session)
    run = repo.get(config_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    summary = _summary(session, run)
    return EvalRunDetail(**summary.model_dump(), results=[_result(r) for r in repo.results(run.id)])
