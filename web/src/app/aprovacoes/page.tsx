"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { decideWorkflowStep, type StepDecision, usePendingApprovals } from "@/lib/api/approvals";
import type { components } from "@/lib/api/schema.d.ts";
import { Button } from "@/components/ui/button";

type ApprovalItem = components["schemas"]["ApprovalItem"];

function when(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function WorkflowApprovalCard({ item }: { item: ApprovalItem }) {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const decide = useMutation({
    mutationFn: (decision: StepDecision) =>
      decideWorkflowStep(item.agent_id, item.run_id, item.session_id, decision),
    onSuccess: () => {
      setFeedback("");
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["runs", item.agent_id] });
    },
  });

  return (
    <li
      className="border-border bg-card flex flex-col gap-3 rounded border p-4"
      aria-label={`Workflow ${item.agent_name}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/workflows/${item.agent_id}`}
          className="text-foreground hover:text-accent text-sm font-medium"
        >
          {item.agent_name || item.agent_id}
        </Link>
        <span className="text-muted-foreground text-[13px]">
          pedido por {item.user_id} · {when(item.created_at)}
        </span>
      </div>
      {item.steps.map((step) => (
        <div key={step.step_id ?? step.step_name} className="flex flex-col gap-1.5">
          <p className="text-foreground text-[13px]">
            Etapa <strong>{step.step_name}</strong>
            {step.when === "after"
              ? " terminou e espera aprovação da saída"
              : " espera confirmação para rodar"}
            {step.retry_count > 0 && ` · tentativa ${step.retry_count + 1}`}
          </p>
          {step.message && <p className="text-muted-foreground text-[13px]">{step.message}</p>}
          {step.output && (
            <pre className="border-border bg-muted text-foreground max-h-64 overflow-auto rounded border p-2 text-[12px] whitespace-pre-wrap">
              {step.output}
            </pre>
          )}
          {step.timeout_at && (
            <p className="text-muted-foreground text-[12px]">
              Sem decisão até {when(step.timeout_at)}, o workflow é cancelado.
            </p>
          )}
        </div>
      ))}
      <textarea
        aria-label="Motivo da recusa"
        value={feedback}
        rows={2}
        maxLength={1000}
        placeholder="Motivo da recusa (opcional; vai para a etapa quando ela é refeita)"
        onChange={(e) => setFeedback(e.target.value)}
        className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] focus:outline-none"
      />
      {decide.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {decide.error.message}
        </p>
      )}
      <div className="flex gap-2">
        <Button
          disabled={decide.isPending}
          onClick={() => decide.mutate({ approve: true })}
          variant="strong"
        >
          Aprovar
        </Button>
        <Button
          disabled={decide.isPending}
          onClick={() => decide.mutate({ approve: false, feedback })}
          variant="destructive"
        >
          Recusar
        </Button>
      </div>
    </li>
  );
}

function ApprovalCard({ item }: { item: ApprovalItem }) {
  const queryClient = useQueryClient();
  const decide = useMutation({
    mutationFn: async (approve: boolean) => {
      // a decisão é o continue do próprio AgentOS, com `confirmed` em cada tool
      const form = new FormData();
      form.append(
        "tools",
        JSON.stringify(item.tools.map((t) => ({ ...t.tool_execution, confirmed: approve }))),
      );
      form.append("session_id", item.session_id ?? "");
      form.append("stream", "false");
      const res = await fetch(`/api/agents/${item.agent_id}/runs/${item.run_id}/continue`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) throw new Error(`Falha ao registrar a decisão (HTTP ${res.status})`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
      void queryClient.invalidateQueries({ queryKey: ["runs", item.agent_id] });
    },
  });

  return (
    <li className="border-border bg-card flex flex-col gap-3 rounded border p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <Link
          href={`/agents/${item.agent_id}`}
          className="text-foreground hover:text-accent text-sm font-medium"
        >
          {item.agent_name || item.agent_id}
        </Link>
        <span className="text-muted-foreground text-[13px]">
          pedido por {item.user_id} ·{" "}
          {new Date(item.created_at).toLocaleString("pt-BR", {
            dateStyle: "short",
            timeStyle: "short",
          })}
        </span>
      </div>

      <ul className="flex flex-col gap-2">
        {item.tools.map((t) => (
          <li key={t.tool_call_id ?? t.tool_name ?? ""}>
            <code className="text-foreground text-[13px]">{t.tool_name}</code>
            <pre className="border-border bg-muted text-muted-foreground mt-1 overflow-x-auto rounded border p-2 text-[12px]">
              {JSON.stringify(t.tool_args ?? {}, null, 2)}
            </pre>
          </li>
        ))}
      </ul>

      {decide.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {decide.error.message}
        </p>
      )}

      <div className="flex gap-2">
        <Button disabled={decide.isPending} onClick={() => decide.mutate(true)} variant="strong">
          Aprovar
        </Button>
        <Button
          disabled={decide.isPending}
          onClick={() => decide.mutate(false)}
          variant="destructive"
        >
          Rejeitar
        </Button>
      </div>
    </li>
  );
}

export default function ApprovalsPage() {
  const { data, isPending, isError } = usePendingApprovals();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Aprovações</h1>
      </header>
      <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Execuções pausadas esperando alguém. Agente com ferramenta marcada para confirmação:
          aprovar executa a ação, rejeitar segue sem ela. Etapa de workflow com revisão humana:
          aprovar segue o fluxo, recusar faz o que a etapa define (encerra, pula ou refaz).
        </p>
        {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive text-[13px]" role="alert">
            Não foi possível carregar as aprovações.
          </p>
        )}
        {data && data.length === 0 && (
          <div className="border-border flex flex-col items-center gap-2 rounded border border-dashed px-6 py-10 text-center">
            <ShieldCheck className="text-accent h-5 w-5" aria-hidden />
            <p className="text-foreground text-sm">Nada aguardando decisão</p>
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="flex flex-col gap-3" aria-live="polite">
            {data.map((item) =>
              item.kind === "workflow" ? (
                <WorkflowApprovalCard key={item.run_id} item={item} />
              ) : (
                <ApprovalCard key={item.run_id} item={item} />
              ),
            )}
          </ul>
        )}
      </main>
    </div>
  );
}
