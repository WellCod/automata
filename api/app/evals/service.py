"""Criação de uma execução da suíte, comum ao painel, aos tokens de integração e ao agendamento.

A rota só traduz o `EvalRunRefused` em HTTP; o agendamento registra o motivo e
segue para o próximo horário. Quem chama agenda o `execute(run.id)`.
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.capabilities import get_capabilities
from app.agents.models_map import demo_replay
from app.models.config import AgentConfig
from app.models.eval import EvalCase, EvalRun
from app.repositories.config import ConfigRepository
from app.repositories.eval import EvalCaseRepository, EvalRunRepository
from app.schemas.eval import EvalRunCreate, EvalTrigger


class EvalRunRefused(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def check_judge(cases: list[EvalCase], judge_model: str | None) -> None:
    if judge_model is not None:
        try:
            caps = get_capabilities(judge_model)
        except ValueError as exc:
            raise EvalRunRefused(422, str(exc)) from exc
        # o juiz responde num schema (aprovado e motivo): sem saída estruturada ele não decide
        if not caps.structured_output:
            raise EvalRunRefused(422, f"'{judge_model}' não tem saída estruturada para julgar")
        return
    has_judge = any(c.get("type") == "judge" for case in cases for c in case.checks)
    if has_judge and not demo_replay():
        raise EvalRunRefused(422, "Escolha o modelo do juiz: há casos com juiz")


def resolve_version(config: AgentConfig, body: EvalRunCreate) -> UUID:
    if body.target == "draft":
        if config.draft_version_id is None:
            raise EvalRunRefused(422, "Config sem rascunho para testar")
        return config.draft_version_id
    if body.target == "current":
        if config.current_version_id is None:
            raise EvalRunRefused(422, "Config sem versão publicada para testar")
        return config.current_version_id
    version_id = body.version_id or config.draft_version_id or config.current_version_id
    if version_id is None:
        raise EvalRunRefused(422, "Config sem versão para testar")
    return version_id


def create_run(
    session: Session,
    config: AgentConfig,
    body: EvalRunCreate,
    *,
    actor: str,
    trigger: EvalTrigger,
    commit: bool = True,
) -> EvalRun:
    """Valida e grava a execução na fila; não roda nada.

    `commit=False` deixa o commit para quem chama: o agendamento grava a execução e
    o próximo horário juntos, com a linha do agendamento ainda travada.
    """
    if config.kind == "workflow":
        # o runner de suíte do Agno roda agente ou time; workflow fica para depois
        raise EvalRunRefused(422, "Workflow ainda não tem suíte de testes")
    version_id = resolve_version(config, body)
    version = ConfigRepository(session).get_version(version_id)
    if version is None or version.config_id != config.id:
        raise EvalRunRefused(422, "Versão não é desta config")
    cases = EvalCaseRepository(session).list_by_config(config.id)
    if not cases:
        raise EvalRunRefused(422, "Suíte sem casos")
    check_judge(cases, body.judge_model)
    runs = EvalRunRepository(session)
    if runs.active(config.id) is not None:
        raise EvalRunRefused(409, "Já há uma execução em andamento")
    run = runs.add(
        EvalRun(
            agent_config_id=config.id,
            version_id=version_id,
            status="queued",
            total=len(cases),
            cases=[
                {"id": str(c.id), "name": c.name, "input": c.input, "checks": c.checks}
                for c in cases
            ],
            judge_model=body.judge_model,
            started_by=actor,
            trigger=trigger,
            target=body.target,
        )
    )
    if commit:
        session.commit()
        session.refresh(run)
    return run
