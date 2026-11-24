// Progresso de um run de workflow a partir do stream do AgentOS. O Agno manda
// StepStarted/StepCompleted por etapa, *ExecutionStarted/Completed por contêiner
// e os eventos do agente ou time da etapa com `step_name`. O `nested_depth` vem 0
// até dentro de paralelo, então a indentação sai da pilha de contêineres abertos.

import { CHECK_ERROR_TYPES } from "@/lib/guardrail-labels";
import type { SseEvent } from "@/lib/sse";

export type ProgressKind = "step" | "parallel" | "condition" | "loop";
export type ProgressStatus = "running" | "done" | "error" | "blocked";

export interface StepProgress {
  id: number;
  name: string;
  kind: ProgressKind;
  status: ProgressStatus;
  depth: number;
  // agente ou time que respondeu a etapa
  who?: string;
  detail?: string;
  output?: string;
}

// etapa esperando revisão humana (ADR-0023), lida do requisito ativo do run
export interface PendingReview {
  stepName: string;
  // loop: fim de uma volta do laço com revisão (ADR-0028)
  when: "before" | "after" | "loop";
  message?: string;
  output?: string;
}

export interface WorkflowProgress {
  status: "idle" | "running" | "done" | "error" | "paused";
  runId: string | null;
  pending: PendingReview | null;
  steps: StepProgress[];
  open: number[];
  final: string;
  error: string | null;
  sessionId: string | null;
  nextId: number;
}

export const EMPTY_PROGRESS: WorkflowProgress = {
  status: "idle",
  runId: null,
  pending: null,
  steps: [],
  open: [],
  final: "",
  error: null,
  sessionId: null,
  nextId: 0,
};

const CONTAINERS: Record<string, ProgressKind> = {
  Parallel: "parallel",
  Condition: "condition",
  Loop: "loop",
};

// campos do evento chegam como unknown; só texto interessa ao progresso
const str = (value: unknown): string | undefined => (typeof value === "string" ? value : undefined);

// última entrada com o nome: numa repetição a mesma etapa aparece uma vez por volta
function lastIndex(steps: StepProgress[], name: string): number {
  for (let i = steps.length - 1; i >= 0; i -= 1) if (steps[i].name === name) return i;
  return -1;
}

// muda a entrada mais recente da etapa sem mexer no estado recebido
function patch(
  progress: WorkflowProgress,
  name: string,
  change: Partial<StepProgress>,
): WorkflowProgress {
  const index = lastIndex(progress.steps, name);
  if (index === -1) return progress;
  const steps = [...progress.steps];
  steps[index] = { ...steps[index], ...change };
  return { ...progress, steps };
}

// entrada nova em execução, indentada pelos contêineres ainda abertos
function push(
  progress: WorkflowProgress,
  name: string,
  kind: ProgressKind,
  detail?: string,
): WorkflowProgress {
  const step: StepProgress = {
    id: progress.nextId,
    name,
    kind,
    status: "running",
    depth: progress.open.length,
    detail,
  };
  return { ...progress, steps: [...progress.steps, step], nextId: progress.nextId + 1 };
}

// o workflow parou: o que ainda estava rodando não vai terminar, e vira erro
function failRunning(progress: WorkflowProgress, detail: string): WorkflowProgress {
  return {
    ...progress,
    steps: progress.steps.map((step) =>
      step.status === "running"
        ? { ...step, status: "error", detail: step.detail ?? detail }
        : step,
    ),
  };
}

// o continue substitui a lista de requisitos e o ativo é o último
export function pendingFrom(requirements: unknown): PendingReview | null {
  if (!Array.isArray(requirements) || requirements.length === 0) return null;
  const active = requirements[requirements.length - 1] as Record<string, unknown>;
  if (active.confirmed === true || active.confirmed === false) return null;
  const after = active.requires_output_review === true;
  const loop = active.step_type === "Loop";
  const output = (active.step_output ?? {}) as { content?: unknown };
  return {
    stepName: str(active.step_name) ?? "etapa",
    when: loop ? "loop" : after ? "after" : "before",
    message: str(after ? active.output_review_message : active.confirmation_message),
    output: after ? str(output.content) : undefined,
  };
}

// resposta do continue sem stream: as etapas depois da revisão não têm progresso próprio
export function applyContinue(
  progress: WorkflowProgress,
  output: Record<string, unknown>,
): WorkflowProgress {
  const status = str(output.status)?.toUpperCase();
  if (status === "PAUSED") {
    return { ...progress, status: "paused", pending: pendingFrom(output.step_requirements) };
  }
  if (status === "COMPLETED") {
    return { ...progress, status: "done", pending: null, final: str(output.content) ?? "" };
  }
  const error =
    status === "CANCELLED"
      ? "Revisão recusada: workflow encerrado."
      : (str(output.content) ?? "O workflow falhou.");
  return { ...progress, status: "error", pending: null, error };
}

// Reducer do stream: cada evento devolve o progresso novo. Eventos sem step_name (fora
// os do workflow) não mexem nas etapas.
export function applyEvent(
  progress: WorkflowProgress,
  { event, data }: SseEvent,
): WorkflowProgress {
  const name = str(data.step_name);
  // a sessão vem no primeiro evento que a traz; o continue e a próxima mensagem usam ela
  const next =
    progress.sessionId === null && str(data.session_id)
      ? { ...progress, sessionId: str(data.session_id)! }
      : progress;

  if (event === "WorkflowStarted") {
    return { ...next, status: "running", runId: str(data.run_id) ?? next.runId };
  }
  if (event === "WorkflowPaused") {
    return {
      ...next,
      status: "paused",
      runId: str(data.run_id) ?? next.runId,
      pending: pendingFrom(data.step_requirements),
    };
  }
  if (event === "WorkflowCompleted") {
    return { ...next, status: "done", final: str(data.content) ?? next.final, open: [] };
  }
  if (event === "WorkflowError" || event === "WorkflowCancelled") {
    const error =
      str(data.error) ??
      str(data.content) ??
      (event === "WorkflowCancelled" ? "Execução cancelada." : "O workflow falhou.");
    return { ...failRunning(next, error), status: "error", error, open: [] };
  }
  if (!name) return next;

  const container = /^(Parallel|Condition|Loop)Execution(Started|Completed)$/.exec(event);
  if (container) {
    const kind = CONTAINERS[container[1]];
    if (container[2] === "Started") {
      const detail =
        kind === "parallel"
          ? `${Number(data.parallel_step_count ?? 0)} ramos ao mesmo tempo`
          : kind === "condition"
            ? data.condition_result
              ? "regra verdadeira"
              : "regra falsa"
            : undefined;
      // o contêiner aberto indenta o que vier até o Completed correspondente
      const pushed = push(next, name, kind, detail);
      return { ...pushed, open: [...pushed.open, pushed.nextId - 1] };
    }
    const done: Partial<StepProgress> = { status: "done" };
    if (kind === "condition") {
      const ran = Number(data.executed_steps ?? 0) > 0;
      done.detail = data.condition_result
        ? "regra verdadeira: rodou o então"
        : ran
          ? "regra falsa: rodou o senão"
          : "regra falsa: pulou";
    }
    if (kind === "loop") done.detail = `${Number(data.total_iterations ?? 0)} volta(s)`;
    const patched = patch(next, name, done);
    return { ...patched, open: patched.open.slice(0, -1) };
  }

  if (event === "LoopIterationStarted") {
    const maxText = data.max_iterations ? ` de ${Number(data.max_iterations)}` : "";
    return patch(next, name, { detail: `volta ${Number(data.iteration ?? 0)}${maxText}` });
  }
  if (event === "StepStarted") return push(next, name, "step");
  if (event === "StepCompleted") {
    const index = lastIndex(next.steps, name);
    // etapa que falhou com "seguir" também fecha com StepCompleted: mantém o erro
    if (index !== -1 && next.steps[index].status !== "running") return next;
    return patch(next, name, { status: "done", output: str(data.content) });
  }
  if (event === "StepError") {
    return patch(next, name, { status: "error", detail: str(data.error) ?? "falhou" });
  }
  if (event === "RunStarted" || event === "TeamRunStarted") {
    const who = str(data.agent_name) ?? str(data.team_name);
    const index = lastIndex(next.steps, name);
    // membros de um time também carregam step_name: vale o primeiro, que é o executor
    if (index === -1 || next.steps[index].who) return next;
    return patch(next, name, { who });
  }
  if (event === "RunError" || event === "TeamRunError") {
    // erro de guardrail é bloqueio, não falha da etapa
    const errorType = str(data.error_type);
    if (errorType && CHECK_ERROR_TYPES.has(errorType)) {
      const extra = (data.additional_data ?? {}) as { rule?: unknown };
      return patch(next, name, {
        status: "blocked",
        detail: str(extra.rule) ?? "guardrail",
        output: str(data.content),
      });
    }
    return patch(next, name, { status: "error", detail: str(data.content) ?? "falhou" });
  }
  return next;
}
