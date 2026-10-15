"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { usePendingApprovals } from "@/lib/api/approvals";
import type { components } from "@/lib/api/schema.d.ts";

type ApprovalItem = components["schemas"]["ApprovalItem"];

const btnCls =
  "inline-flex h-7 items-center rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40";

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
        <button
          type="button"
          disabled={decide.isPending}
          onClick={() => decide.mutate(true)}
          className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
        >
          Aprovar
        </button>
        <button
          type="button"
          disabled={decide.isPending}
          onClick={() => decide.mutate(false)}
          className={`${btnCls} border-destructive text-destructive`}
        >
          Rejeitar
        </button>
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
          Execuções pausadas porque o agente pediu uma ferramenta marcada para confirmação. Aprovar
          executa a ação; rejeitar segue o run sem ela.
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
            <p className="text-foreground text-sm">Nada aguardando confirmação</p>
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="flex flex-col gap-3" aria-live="polite">
            {data.map((item) => (
              <ApprovalCard key={item.run_id} item={item} />
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
