import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";

export function usePendingApprovals() {
  return useQuery({
    queryKey: ["approvals"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/approvals");
      if (res.error) throw new Error("Falha ao carregar aprovações");
      return res.data!;
    },
    refetchInterval: 10_000,
  });
}

export interface StepDecision {
  approve: boolean;
  // na recusa com "refaz com o motivo", vai para a etapa na nova tentativa
  feedback?: string;
}

/**
 * Decide a etapa do workflow pausada (ADR-0023), pelo continue do AgentOS.
 *
 * O continue substitui a lista de requisitos do run, e o ativo é o último: lê a
 * lista do run, marca o último e devolve a lista inteira.
 */
export async function decideWorkflowStep(
  workflowId: string,
  runId: string,
  sessionId: string | null | undefined,
  decision: StepDecision,
): Promise<Record<string, unknown>> {
  const query = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const run = await fetch(`/api/workflows/${workflowId}/runs/${runId}${query}`);
  if (!run.ok) throw new Error(`Falha ao ler a execução (HTTP ${run.status})`);
  const data = (await run.json()) as { step_requirements?: Record<string, unknown>[] | null };
  const requirements = data.step_requirements ?? [];
  if (requirements.length === 0) throw new Error("A execução não tem etapa esperando revisão");
  const active = {
    ...requirements[requirements.length - 1],
    confirmed: decision.approve,
    ...(!decision.approve && decision.feedback?.trim()
      ? { rejection_feedback: decision.feedback.trim() }
      : {}),
  };
  const form = new FormData();
  form.append("step_requirements", JSON.stringify([...requirements.slice(0, -1), active]));
  form.append("session_id", sessionId ?? "");
  form.append("stream", "false");
  const res = await fetch(`/api/workflows/${workflowId}/runs/${runId}/continue`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`Falha ao registrar a decisão (HTTP ${res.status})`);
  return (await res.json()) as Record<string, unknown>;
}
