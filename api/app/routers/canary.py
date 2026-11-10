"""Liberação gradual de versão (ADR-0040): ligar, comparar, promover e desligar o canário."""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.agents.canary import MAX_PERCENT
from app.authz import Scope, require_scopes
from app.db import SessionDep
from app.evals.gate import draft_verdict
from app.models.config import AgentConfig, AgentConfigVersion
from app.models.eval import EvalRun
from app.models.run import AgentRun
from app.models.usage import UsageEvent
from app.repositories.config import ConfigRepository
from app.repositories.knowledge_base import KnowledgeBaseRepository
from app.repositories.mcp_server import McpServerRepository
from app.schemas.config import ConfigPayloadStatus
from app.services.config import ConfigService, stop_canary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/configs/{config_id}/canary", tags=["canary"])
_READ = [Depends(require_scopes(Scope.CONFIGS_READ))]
_PUBLISH = [Depends(require_scopes(Scope.CONFIGS_PUBLISH))]


class CanaryStart(BaseModel):
    # vazio publica o rascunho como versão nova, sem mover a vigente
    version_id: UUID | None = None
    percent: int = Field(ge=1, le=MAX_PERCENT)


class CanaryPercent(BaseModel):
    percent: int = Field(ge=1, le=MAX_PERCENT)


class SuiteResult(BaseModel):
    status: str
    total: int
    passed: int
    failed: int
    created_at: datetime


class VersionStats(BaseModel):
    version_id: UUID
    version_number: int
    runs: int
    errors: int
    error_rate: float
    p50_ms: float | None
    p95_ms: float | None
    avg_cost: float | None
    suite: SuiteResult | None


class CanaryState(BaseModel):
    active: bool
    percent: int | None
    started_at: datetime | None
    current: VersionStats | None
    canary: VersionStats | None


def _config_or_404(session: Session, config_id: UUID) -> AgentConfig:
    config = ConfigRepository(session).get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Config não encontrada")
    if config.kind not in ("agent", "team"):
        raise HTTPException(status_code=422, detail="Canário vale para agente e time")
    return config


def version_stats(
    session: Session, config_id: UUID, version: AgentConfigVersion, since: datetime | None
) -> VersionStats:
    """Conversas da versão desde o início do canário; testes da suíte ficam fora."""
    where: list[Any] = [
        AgentRun.agent_config_id == config_id,
        AgentRun.version_id == version.id,
        AgentRun.eval_run_id.is_(None),
    ]
    if since is not None:
        where.append(AgentRun.created_at >= since)
    row = session.execute(
        select(
            func.count(AgentRun.id),
            func.coalesce(func.sum(case((AgentRun.status == "error", 1), else_=0)), 0),
            func.percentile_cont(0.5).within_group(AgentRun.duration_ms),
            func.percentile_cont(0.95).within_group(AgentRun.duration_ms),
        ).where(*where)
    ).one()
    runs, errors = int(row[0]), int(row[1])
    cost = session.scalar(
        select(func.sum(UsageEvent.cost)).where(
            UsageEvent.run_id.in_(select(AgentRun.run_id).where(*where))
        )
    )
    latest = session.scalars(
        select(EvalRun)
        .where(EvalRun.version_id == version.id)
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    ).first()
    return VersionStats(
        version_id=version.id,
        version_number=version.version_number,
        runs=runs,
        errors=errors,
        error_rate=errors / runs if runs else 0.0,
        p50_ms=float(row[2]) if row[2] is not None else None,
        p95_ms=float(row[3]) if row[3] is not None else None,
        avg_cost=float(cost) / runs if cost is not None and runs else None,
        suite=SuiteResult(
            status=latest.status,
            total=latest.total,
            passed=latest.passed,
            failed=latest.failed,
            created_at=latest.created_at,
        )
        if latest is not None
        else None,
    )


def _state(session: Session, config: AgentConfig) -> CanaryState:
    repo = ConfigRepository(session)
    since = config.canary_started_at
    current = repo.get_version(config.current_version_id) if config.current_version_id else None
    canary = repo.get_version(config.canary_version_id) if config.canary_version_id else None
    return CanaryState(
        active=canary is not None,
        percent=config.canary_percent,
        started_at=since,
        current=version_stats(session, config.id, current, since) if current else None,
        canary=version_stats(session, config.id, canary, since) if canary else None,
    )


@router.get("", response_model=CanaryState, dependencies=_READ)
def get_canary(config_id: UUID, session: SessionDep) -> CanaryState:
    return _state(session, _config_or_404(session, config_id))


@router.post("", response_model=CanaryState, status_code=201, dependencies=_PUBLISH)
def start_canary(config_id: UUID, body: CanaryStart, session: SessionDep) -> CanaryState:
    config = _config_or_404(session, config_id)
    if config.canary_version_id is not None:
        raise HTTPException(status_code=409, detail="Já há um canário; promova ou desligue antes")
    if config.current_version_id is None:
        raise HTTPException(status_code=409, detail="Publique uma primeira versão antes")
    repo = ConfigRepository(session)
    if body.version_id is None:
        # mesmo gate da publicação: o canário recebe conversa de verdade
        if config.require_passing_evals:
            verdict = draft_verdict(session, config)
            if not verdict.ok:
                raise HTTPException(
                    status_code=409, detail=f"Canário exige a suíte verde: {verdict.reason}"
                )
        service = ConfigService(
            repo, McpServerRepository(session), KnowledgeBaseRepository(session)
        )
        try:
            version = service.publish_canary(config_id, author="panel")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        found = repo.get_version(body.version_id)
        if (
            found is None
            or found.config_id != config_id
            or found.status != ConfigPayloadStatus.published
        ):
            raise HTTPException(
                status_code=422, detail="Versão publicada deste config não encontrada"
            )
        if found.id == config.current_version_id:
            raise HTTPException(status_code=422, detail="Essa já é a versão vigente")
        version = found
    config.canary_version_id = version.id
    config.canary_percent = body.percent
    config.canary_started_at = datetime.now(UTC)
    session.commit()
    logger.info(
        "canário ligado",
        extra={"config_id": str(config_id), "version_id": str(version.id), "percent": body.percent},
    )
    return _state(session, config)


@router.patch("", response_model=CanaryState, dependencies=_PUBLISH)
def change_percent(config_id: UUID, body: CanaryPercent, session: SessionDep) -> CanaryState:
    config = _config_or_404(session, config_id)
    if config.canary_version_id is None:
        raise HTTPException(status_code=409, detail="Não há canário ligado")
    config.canary_percent = body.percent
    session.commit()
    return _state(session, config)


@router.post("/promote", response_model=CanaryState, dependencies=_PUBLISH)
def promote(config_id: UUID, session: SessionDep) -> CanaryState:
    config = _config_or_404(session, config_id)
    if config.canary_version_id is None:
        raise HTTPException(status_code=409, detail="Não há canário ligado")
    promoted = config.canary_version_id
    ConfigRepository(session).set_current_version(config, promoted)
    stop_canary(config)
    session.commit()
    logger.info(
        "canário promovido", extra={"config_id": str(config_id), "version_id": str(promoted)}
    )
    return _state(session, config)


@router.delete("", response_model=CanaryState, dependencies=_PUBLISH)
def stop(config_id: UUID, session: SessionDep) -> CanaryState:
    config = _config_or_404(session, config_id)
    stop_canary(config)
    session.commit()
    return _state(session, config)
