"""Gate de publicação por suíte verde (ADR-0015).

Cada rascunho salvo é uma versão nova, então o resultado vale para o
`draft_version_id` atual e nenhum outro: editar o rascunho invalida a execução
anterior sem precisar comparar payload.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.config import AgentConfig
from app.models.eval import EvalRun


@dataclass
class GateVerdict:
    ok: bool
    reason: str | None
    run: EvalRun | None


def latest_run(session: Session, config: AgentConfig) -> EvalRun | None:
    if config.draft_version_id is None:
        return None
    stmt = (
        select(EvalRun)
        .where(EvalRun.version_id == config.draft_version_id)
        .order_by(EvalRun.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def draft_verdict(session: Session, config: AgentConfig) -> GateVerdict:
    if config.draft_version_id is None:
        return GateVerdict(False, "não há rascunho para publicar", None)
    run = latest_run(session, config)
    if run is None:
        return GateVerdict(False, "a suíte ainda não rodou no rascunho atual", None)
    if run.status in ("queued", "running"):
        return GateVerdict(False, "a suíte ainda está rodando no rascunho atual", run)
    if run.status == "failed":
        return GateVerdict(False, "a última execução no rascunho atual falhou", run)
    if run.total == 0 or run.passed != run.total:
        pending = run.total - run.passed
        return GateVerdict(
            False, f"{pending} de {run.total} casos não passaram no rascunho atual", run
        )
    return GateVerdict(True, None, run)
