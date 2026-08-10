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

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-foreground text-[13px] font-medium">
        Uso · {period.slice(0, 4)}/{period.slice(4)}
      </h2>

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && <p className="text-destructive text-[13px]">Erro ao carregar uso.</p>}

      {!isPending && !isError && (
        <dl className="grid grid-cols-3 gap-2">
          <div className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
            <dt className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
              Execuções
            </dt>
            <dd className="text-foreground text-[13px] font-medium">{data?.run_count ?? 0}</dd>
          </div>
          <div className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
            <dt className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
              Tokens
            </dt>
            <dd className="text-foreground text-[13px] font-medium">
              {formatTokens(data?.total_tokens ?? 0)}
            </dd>
          </div>
          <div className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
            <dt className="text-label text-[11px] font-medium tracking-[0.05em] uppercase">
              Custo
            </dt>
            <dd className="text-foreground text-[13px] font-medium">
              {formatCost(data?.cost ?? null)}
            </dd>
          </div>
        </dl>
      )}
    </div>
  );
}
