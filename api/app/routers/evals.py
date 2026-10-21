"""Casos de teste por agente e time (ADR-0015)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.models.config import AgentConfig
from app.models.eval import EvalCase
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository
from app.schemas.eval import MAX_CASES, EvalCaseInput, EvalCaseResponse

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
