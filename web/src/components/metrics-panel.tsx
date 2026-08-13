"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type AgentMetricsResponse = components["schemas"]["AgentMetricsResponse"];

interface Props {
  agentId: string;
}

const PERIODS = [
  { value: "7d", label: "7 dias" },
  { value: "30d", label: "30 dias" },
  { value: "90d", label: "90 dias" },
] as const;

type Period = (typeof PERIODS)[number]["value"];

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatRate(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="border-border bg-card flex flex-col gap-0.5 rounded border px-3 py-2.5">
      <span className="text-muted-foreground text-[10px] tracking-[0.05em] uppercase">{label}</span>
      <span className="text-foreground text-[20px] leading-tight font-semibold">{value}</span>
      {sub && <span className="text-muted-foreground text-[11px]">{sub}</span>}
    </div>
  );
}

export function MetricsPanel({ agentId }: Props) {
  const [period, setPeriod] = useState<Period>("30d");

  const { data, isPending, isError } = useQuery<AgentMetricsResponse>({
    queryKey: ["metrics", agentId, period],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/metrics", {
        params: { path: { config_id: agentId }, query: { period } },
      });
      if (res.error) throw new Error("Falha ao carregar métricas");
      return res.data!;
    },
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-1">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            onClick={() => setPeriod(p.value)}
            className={`rounded px-2 py-1 text-[11px] font-medium transition-colors ${
              period === p.value
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && <p className="text-[13px] text-red-400">Falha ao carregar métricas.</p>}

      {data && (
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label="Total de runs" value={String(data.total_runs)} />
          <MetricCard
            label="Taxa de erro"
            value={formatRate(data.error_rate)}
            sub={data.total_runs === 0 ? "sem dados" : undefined}
          />
          <MetricCard label="Latência p50" value={formatMs(data.p50_ms)} />
          <MetricCard label="Latência p95" value={formatMs(data.p95_ms)} />
        </div>
      )}
    </div>
  );
}
