"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type RollupItem = components["schemas"]["RollupItem"];

interface Props {
  agentId: string;
}

function currentPeriod(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  return `${y}${m}`;
}

function formatCost(cost: number | null): string {
  if (cost === null) return "—";
  return cost.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
  });
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)} k`;
  return String(n);
}

export function CostPanel({ agentId }: Props) {
  const period = currentPeriod();

  const { data, isPending, isError } = useQuery<RollupItem | null>({
    queryKey: ["usage:rollup", agentId, period],
    queryFn: async () => {
      const res = await client.GET("/api/v1/usage/rollup", {
        params: { query: { agent_id: agentId, period } },
      });
      if (res.error) throw new Error("Falha ao carregar uso");
      return res.data?.[0] ?? null;
    },
  });

  const stats = [
    { label: "Execuções", value: String(data?.run_count ?? 0) },
    { label: "Tokens", value: formatTokens(data?.total_tokens ?? 0) },
    { label: "Custo", value: formatCost(data?.cost ?? null) },
  ];

  return (
    <div className="flex flex-col gap-3">
      <span className="text-muted-foreground text-[11px] font-medium tracking-[0.05em] uppercase">
        Uso · {period.slice(0, 4)}/{period.slice(4)}
      </span>

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && <p className="text-destructive text-[13px]">Erro ao carregar uso.</p>}

      {!isPending && !isError && (
        <div className="grid grid-cols-3 gap-2">
          {stats.map(({ label, value }) => (
            <div
              key={label}
              className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2"
            >
              <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
                {label}
              </span>
              <span className="text-foreground text-[13px] font-medium">{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
