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
    <div className="rounded-lg border border-zinc-200 p-4">
      <h2 className="text-sm font-medium text-zinc-700">
        Uso no mês ({period.slice(0, 4)}/{period.slice(4)})
      </h2>

      {isPending && <p className="mt-3 text-xs text-zinc-400">Carregando…</p>}

      {isError && <p className="mt-3 text-xs text-red-500">Erro ao carregar uso.</p>}

      {!isPending && !isError && (
        <dl className="mt-3 grid grid-cols-3 gap-4">
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs text-zinc-400">Execuções</dt>
            <dd className="text-sm font-medium text-zinc-900">{data?.run_count ?? 0}</dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs text-zinc-400">Tokens</dt>
            <dd className="text-sm font-medium text-zinc-900">
              {formatTokens(data?.total_tokens ?? 0)}
            </dd>
          </div>
          <div className="flex flex-col gap-0.5">
            <dt className="text-xs text-zinc-400">Custo</dt>
            <dd className="text-sm font-medium text-zinc-900">{formatCost(data?.cost ?? null)}</dd>
          </div>
        </dl>
      )}
    </div>
  );
}
