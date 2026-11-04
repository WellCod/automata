"""Consumo de chamada de modelo fora do run, atribuído ao agente que a causou.

O HyDE da busca (ADR-0017) e o classificador de entrada (ADR-0030) chamam um modelo
que o RunMetrics do Agno não vê. O consumo vira `usage_event` do agente, com o
`run_id`, e entra no custo e no orçamento como o resto.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import get_engine
from app.evals.judge import JudgeUsage
from app.pricing import cost_or_estimate
from app.repositories.usage import UsageRepository


@dataclass(frozen=True)
class Caller:
    """Run que fez a chamada, para o consumo cair no agente certo."""

    agent_config_id: UUID
    user_id: str
    run_id: str | None = None


def record_side_cost(caller: Caller, model_id: str, cost: float) -> None:
    """Chamada cobrada por unidade e não por token, como a busca do cross-encoder (ADR-0033)."""
    from app.agents.tracking import current_eval_run

    evaluation = current_eval_run.get()
    with Session(get_engine()) as session:
        UsageRepository(session).record_event(
            agent_config_id=caller.agent_config_id,
            user_id=evaluation.actor if evaluation else caller.user_id,
            model_id=model_id,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            cost=cost,
            run_id=caller.run_id,
            eval_run_id=evaluation.eval_run_id if evaluation else None,
        )
        session.commit()


def record_side_usage(caller: Caller, model_id: str, usage: JudgeUsage) -> None:
    if not usage.total_tokens:
        return
    from app.agents.tracking import current_eval_run

    evaluation = current_eval_run.get()
    with Session(get_engine()) as session:
        UsageRepository(session).record_event(
            agent_config_id=caller.agent_config_id,
            user_id=evaluation.actor if evaluation else caller.user_id,
            model_id=model_id,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cost=cost_or_estimate(usage.cost, model_id, usage.input_tokens, usage.output_tokens),
            run_id=caller.run_id,
            eval_run_id=evaluation.eval_run_id if evaluation else None,
        )
        session.commit()
