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

export interface WorkflowProgress {
  status: "idle" | "running" | "done" | "error";
  steps: StepProgress[];
  open: number[];
  final: string;
  error: string | null;
  sessionId: string | null;
  nextId: number;
}

export const EMPTY_PROGRESS: WorkflowProgress = {
  status: "idle",
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

const str = (v: unknown): string | undefined => (typeof v === "string" ? v : undefined);

// última entrada com o nome: numa repetição a mesma etapa aparece uma vez por volta
function lastIndex(steps: StepProgress[], name: string): number {
  for (let i = steps.length - 1; i >= 0; i -= 1) if (steps[i].name === name) return i;
  return -1;
}

function patch(p: WorkflowProgress, name: string, change: Partial<StepProgress>): WorkflowProgress {
  const i = lastIndex(p.steps, name);
  if (i === -1) return p;
  const steps = [...p.steps];
  steps[i] = { ...steps[i], ...change };
  return { ...p, steps };
}

function push(
  p: WorkflowProgress,
  name: string,
  kind: ProgressKind,
  detail?: string,
): WorkflowProgress {
  const step: StepProgress = {
    id: p.nextId,
    name,
    kind,
    status: "running",
    depth: p.open.length,
    detail,
  };
  return { ...p, steps: [...p.steps, step], nextId: p.nextId + 1 };
}

function failRunning(p: WorkflowProgress, detail: string): WorkflowProgress {
  return {
    ...p,
    steps: p.steps.map((s) =>
      s.status === "running" ? { ...s, status: "error", detail: s.detail ?? detail } : s,
    ),
  };
}

export function applyEvent(p: WorkflowProgress, { event, data }: SseEvent): WorkflowProgress {
  const name = str(data.step_name);
  const next =
    p.sessionId === null && str(data.session_id) ? { ...p, sessionId: str(data.session_id)! } : p;

  if (event === "WorkflowStarted") return { ...next, status: "running" };
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
    const max = data.max_iterations ? ` de ${Number(data.max_iterations)}` : "";
    return patch(next, name, { detail: `volta ${Number(data.iteration ?? 0)}${max}` });
  }
  if (event === "StepStarted") return push(next, name, "step");
  if (event === "StepCompleted") {
    const i = lastIndex(next.steps, name);
    // etapa que falhou com "seguir" também fecha com StepCompleted: mantém o erro
    if (i !== -1 && next.steps[i].status !== "running") return next;
    return patch(next, name, { status: "done", output: str(data.content) });
  }
  if (event === "StepError") {
    return patch(next, name, { status: "error", detail: str(data.error) ?? "falhou" });
  }
  if (event === "RunStarted" || event === "TeamRunStarted") {
    const who = str(data.agent_name) ?? str(data.team_name);
    const i = lastIndex(next.steps, name);
    // membros de um time também carregam step_name: vale o primeiro, que é o executor
    if (i === -1 || next.steps[i].who) return next;
    return patch(next, name, { who });
  }
  if (event === "RunError" || event === "TeamRunError") {
    const type = str(data.error_type);
    if (type && CHECK_ERROR_TYPES.has(type)) {
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
