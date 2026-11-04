"""Workflow por request a partir da versão publicada (ADR-0014).

A árvore do payload vira Step, Parallel, Condition e Loop do Agno, montados do
zero a cada request: uma instância nova de agente ou time por etapa (ramos
paralelos não podem compartilhar estado nem conexão MCP) e o user_id do run,
que o Agno não repassa às etapas por conta própria.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from agno.db.base import AsyncBaseDb, BaseDb
from agno.factory.utils import FactoryValidationError, RequestContext
from agno.workflow import Condition, Loop, OnError, Parallel, Router, Step, StepInput, StepOutput
from agno.workflow.factory import WorkflowFactory
from agno.workflow.types import HumanReview, OnReject, OnTimeout, StepType
from agno.workflow.workflow import STEP_TYPE_MAPPING

from app.agents.factory import (
    FactoryInput,
    ResolvedTeam,
    ResolvedVersion,
    agent_from,
    load_team,
    load_version,
    team_from,
)
from app.agents.tracking import RunTracking, TrackedWorkflow
from app.schemas.workflow import (
    STEP_REF,
    ConditionNode,
    LoopNode,
    ParallelNode,
    RouterNode,
    StepNode,
    StepReview,
    WorkflowNode,
    WorkflowRule,
)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def rule_matches(rule: WorkflowRule, text: str) -> bool:
    """Regra própria no lugar de CEL: sem pacote extra e sem `False` silencioso."""
    alvo = text.strip().casefold()
    valor = rule.value.strip().casefold()
    if rule.kind == "always":
        return True
    if rule.kind == "contains":
        return valor in alvo
    if rule.kind == "not_contains":
        return valor not in alvo
    if rule.kind == "starts_with":
        return alvo.startswith(valor)
    if rule.kind == "empty":
        return alvo == ""
    return alvo != ""


def condition_evaluator(rule: WorkflowRule) -> Any:
    def evaluate(step_input: StepInput) -> bool:
        if rule.source == "input":
            return rule_matches(rule, _text(step_input.input))
        # conteúdo mais profundo da última etapa: depois de um paralelo ou condição o
        # previous_step_content do Agno é a frase-resumo do container, não a resposta
        previous = step_input.get_last_step_content() or step_input.previous_step_content
        return rule_matches(rule, _text(previous))

    return evaluate


def _deepest(output: StepOutput) -> str:
    if output.steps:
        return _deepest(output.steps[-1])
    return _text(output.content)


def loop_end_condition(rule: WorkflowRule) -> Any:
    def done(outputs: list[StepOutput]) -> bool:
        return bool(outputs) and rule_matches(rule, _deepest(outputs[-1]))

    return done


@dataclass
class ResolvedStep:
    node: StepNode
    agent: ResolvedVersion | None = None
    team: ResolvedTeam | None = None


@dataclass
class ResolvedWorkflow:
    name: str
    description: str
    steps: list[WorkflowNode]
    # resolução por etapa: a mesma config em duas etapas ganha instâncias separadas
    executors: dict[str, ResolvedStep]
    history_runs: int = 0


def history_kwargs(resolved: ResolvedWorkflow) -> dict[str, Any]:
    """Histórico do workflow nas etapas (ADR-0038); desligado, o padrão do Agno."""
    if not resolved.history_runs:
        return {}
    return {"add_workflow_history_to_steps": True, "num_history_runs": resolved.history_runs}


def load_workflow(config_id: UUID, version_id: UUID | None) -> ResolvedWorkflow:
    resolved = load_version(config_id, version_id)
    workflow = resolved.payload.workflow
    if workflow is None:
        raise FactoryValidationError(f"Config {config_id} não é um workflow")
    from app.schemas.workflow import step_nodes

    executors: dict[str, ResolvedStep] = {}
    for node in step_nodes(workflow.steps):
        if node.agent_id is not None:
            executors[node.name] = ResolvedStep(
                node, agent=load_version(node.agent_id, node.version_id)
            )
        elif node.team_id is not None:
            executors[node.name] = ResolvedStep(node, team=load_team(node.team_id, node.version_id))
    return ResolvedWorkflow(
        resolved.name, resolved.description, workflow.steps, executors, workflow.history_runs
    )


def _find(outputs: dict[str, StepOutput] | None, name: str) -> StepOutput | None:
    """Saída de uma etapa pelo nome, também dentro de paralelo, condição, laço e roteador."""
    pending = list((outputs or {}).values())
    while pending:
        output = pending.pop(0)
        if output.step_name == name:
            return output
        pending.extend(output.steps or [])
    return None


def render_input(
    mode: str, template: str | None, message: Any, outputs: dict[str, StepOutput] | None
) -> Any:
    """Entrada da etapa (ADR-0038); `previous` fica com a montagem do Agno."""
    if mode == "original":
        return message
    previous = _deepest(list(outputs.values())[-1]) if outputs else ""

    def named(match: re.Match[str]) -> str:
        found = _find(outputs, match.group(1).strip())
        return _deepest(found) if found else ""

    text = STEP_REF.sub(named, template or "")
    return text.replace("{entrada}", _text(message)).replace("{anterior}", previous)


class MappedStep(Step):
    """Etapa que escolhe o que o agente recebe, no lugar da saída anterior."""

    def __init__(self, *args: Any, input_mode: str, template: str | None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.input_mode = input_mode
        self.template = template

    def _prepare_message(
        self, message: Any, previous_step_outputs: dict[str, StepOutput] | None = None
    ) -> Any:
        return render_input(self.input_mode, self.template, message, previous_step_outputs)


# o Agno descreve as etapas pelo tipo exato (STEP_TYPE_MAPPING[type(step)]): sem isto a
# subclasse quebra ao montar os dados do workflow
STEP_TYPE_MAPPING[MappedStep] = StepType.STEP


def router_selector(routes: list[tuple[WorkflowRule, str]], default: str | None) -> Any:
    def select(step_input: StepInput) -> Any:
        previous = step_input.get_last_step_content() or step_input.previous_step_content
        for rule, name in routes:
            text = step_input.input if rule.source == "input" else previous
            if rule_matches(rule, _text(text)):
                return name
        # nenhum caminho: o padrão, ou nada roda e a saída anterior segue
        return default if default else []

    return select


def _step(resolved: ResolvedStep) -> Step:
    node = resolved.node
    if resolved.agent is not None:
        assert node.agent_id is not None
        executor: RunTracking = agent_from(node.agent_id, resolved.agent, tracked=True)  # type: ignore[assignment]
        kind = {"agent": executor}
    else:
        assert node.team_id is not None and resolved.team is not None
        executor = team_from(node.team_id, resolved.team)
        kind = {"team": executor}
    # erro ou bloqueio na etapa vira exceção: on_error e max_retries do Agno passam a valer
    executor.automata_raise_on_error = True
    if node.input != "previous":
        return MappedStep(
            name=node.name,
            max_retries=node.max_retries,
            human_review=human_review_for(node),
            input_mode=node.input,
            template=node.template,
            **kind,
        )
    return Step(
        name=node.name,
        max_retries=node.max_retries,
        human_review=human_review_for(node),
        **kind,  # type: ignore[arg-type]
    )


# refazer na recusa: até 3 vezes, como o max_retries da etapa
REVIEW_RETRIES = 3


def human_review_for(node: StepNode) -> HumanReview:
    on_error = OnError.fail if node.on_error == "stop" else OnError.skip
    review: StepReview | None = node.review
    if review is None:
        return HumanReview(on_error=on_error)
    message = review.message.strip() or None
    return HumanReview(
        requires_confirmation=review.when == "before",
        confirmation_message=message if review.when == "before" else None,
        requires_output_review=review.when == "after",
        output_review_message=message if review.when == "after" else None,
        on_reject=OnReject(review.on_reject),
        on_error=on_error,
        max_retries=REVIEW_RETRIES,
        timeout=review.timeout_hours * 3600 if review.timeout_hours else None,
        on_timeout=OnTimeout.cancel,
    )


def loop_review_for(node: LoopNode) -> HumanReview | None:
    """Revisão ao fim de cada volta (ADR-0028): recusar sempre pede outra volta."""
    if node.review is None:
        return None
    hours = node.review.timeout_hours
    return HumanReview(
        requires_iteration_review=True,
        iteration_review_message=node.review.message.strip() or None,
        on_reject=OnReject.retry,
        timeout=hours * 3600 if hours else None,
        on_timeout=OnTimeout.cancel,
    )


def build_nodes(nodes: list[WorkflowNode], resolved: ResolvedWorkflow) -> list[Any]:
    built: list[Any] = []
    for node in nodes:
        if isinstance(node, StepNode):
            built.append(_step(resolved.executors[node.name]))
        elif isinstance(node, ParallelNode):
            branches: list[Any] = [_step(resolved.executors[b.name]) for b in node.branches]
            built.append(Parallel(*branches, name=node.name))
        elif isinstance(node, ConditionNode):
            built.append(
                Condition(
                    name=node.name,
                    evaluator=condition_evaluator(node.rule),
                    steps=build_nodes(node.steps, resolved),
                    else_steps=build_nodes(node.else_steps, resolved) or None,
                )
            )
        elif isinstance(node, RouterNode):
            steps = [r.step for r in node.routes] + ([node.default] if node.default else [])
            built.append(
                Router(
                    name=node.name,
                    choices=[_step(resolved.executors[s.name]) for s in steps],
                    selector=router_selector(
                        [(r.rule, r.step.name) for r in node.routes],
                        node.default.name if node.default else None,
                    ),
                )
            )
        elif isinstance(node, LoopNode):
            built.append(
                Loop(
                    name=node.name,
                    steps=build_nodes(node.steps, resolved),
                    max_iterations=node.max_iterations,
                    end_condition=loop_end_condition(node.until) if node.until else None,
                    human_review=loop_review_for(node),
                )
            )
    return built


def make_workflow_factory(config_id: UUID, db: BaseDb | AsyncBaseDb) -> WorkflowFactory:
    async def build(ctx: RequestContext) -> TrackedWorkflow:
        version_id = ctx.input.version_id if isinstance(ctx.input, FactoryInput) else None
        resolved = await asyncio.to_thread(load_workflow, config_id, version_id)
        workflow = TrackedWorkflow(
            id=str(config_id),
            name=resolved.name,
            description=resolved.description,
            steps=build_nodes(resolved.steps, resolved),
            # sem isso as etapas rodam com o user_id da instância (None) e viram anônimas
            user_id=ctx.user_id,
            **history_kwargs(resolved),
        )
        workflow.automata_config_id = config_id
        return workflow

    return WorkflowFactory(
        id=str(config_id),
        db=db,
        factory=build,
        input_schema=FactoryInput,
    )
