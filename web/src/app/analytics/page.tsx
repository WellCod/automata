"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type GlobalMetricsSummary = components["schemas"]["GlobalMetricsSummary"];
type RollupItem = components["schemas"]["RollupItem"];

const PERIODS = [
  { value: "7d", label: "7 dias" },
  { value: "30d", label: "30 dias" },
  { value: "90d", label: "90 dias" },
] as const;

type Period = (typeof PERIODS)[number]["value"];

function currentPeriod(): string {
  const now = new Date();
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function formatMs(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)} k`;
  return String(n);
}

function formatCost(cost: number | null): string {
  if (cost === null) return "—";
  return cost.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
  });
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-border bg-card flex flex-col gap-1 rounded border px-4 py-3">
      <span className="text-muted-foreground text-[10px] font-medium tracking-[0.05em] uppercase">
        {label}
      </span>
      <span className="text-foreground text-[22px] leading-tight font-semibold">{value}</span>
    </div>
  );
}

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<Period>("30d");
  const calPeriod = currentPeriod();

  const { data: summary, isPending: summaryPending } = useQuery<GlobalMetricsSummary>({
    queryKey: ["analytics:summary", period],
    queryFn: async () => {
      const res = await client.GET("/api/v1/metrics/summary", {
        params: { query: { period } },
      });
      if (res.error) throw new Error("Falha ao carregar sumário");
      return res.data!;
    },
  });

  const { data: rollup, isPending: rollupPending } = useQuery<RollupItem[]>({
    queryKey: ["analytics:rollup", calPeriod],
    queryFn: async () => {
      const res = await client.GET("/api/v1/usage/rollup", {
        params: { query: { period: calPeriod } },
      });
      if (res.error) throw new Error("Falha ao carregar uso");
      return res.data ?? [];
    },
  });

  return (
    <div className="w-full px-6 py-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-foreground text-[18px] font-semibold">Analytics</h1>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              type="button"
              onClick={() => setPeriod(p.value)}
              className={`rounded px-3 py-1 text-[12px] font-medium transition-colors ${
                period === p.value
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {summaryPending ? (
        <p className="text-muted-foreground text-[13px]">Carregando…</p>
      ) : (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard label="Total de runs" value={String(summary?.total_runs ?? 0)} />
          <SummaryCard
            label="Taxa de erro"
            value={`${((summary?.error_rate ?? 0) * 100).toFixed(1)}%`}
          />
          <SummaryCard label="p50 latência" value={formatMs(summary?.p50_ms ?? null)} />
          <SummaryCard label="p95 latência" value={formatMs(summary?.p95_ms ?? null)} />
          <SummaryCard label="Total tokens" value={formatTokens(summary?.total_tokens ?? 0)} />
          <SummaryCard label="Custo estimado" value={formatCost(summary?.total_cost ?? null)} />
        </div>
      )}

      <div>
        <h2 className="text-foreground mb-3 text-[13px] font-medium">
          Uso por agente · {calPeriod.slice(0, 4)}/{calPeriod.slice(4)}
        </h2>

        {rollupPending ? (
          <p className="text-muted-foreground text-[13px]">Carregando…</p>
        ) : !rollup || rollup.length === 0 ? (
          <p className="text-muted-foreground text-[13px]">Nenhum dado de uso neste mês.</p>
        ) : (
          <div className="border-border overflow-hidden rounded border">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-border bg-card border-b">
                  <th className="text-muted-foreground px-4 py-2 text-left font-medium">Agente</th>
                  <th className="text-muted-foreground px-4 py-2 text-right font-medium">
                    Execuções
                  </th>
                  <th className="text-muted-foreground px-4 py-2 text-right font-medium">Tokens</th>
                  <th className="text-muted-foreground px-4 py-2 text-right font-medium">Custo</th>
                </tr>
              </thead>
              <tbody>
                {rollup.map((row) => (
                  <tr key={row.agent_config_id} className="border-border border-b last:border-0">
                    <td className="text-muted-foreground px-4 py-2 font-mono text-[11px]">
                      {row.agent_config_id.slice(0, 8)}…
                    </td>
                    <td className="text-foreground px-4 py-2 text-right">{row.run_count}</td>
                    <td className="text-foreground px-4 py-2 text-right">
                      {formatTokens(row.total_tokens)}
                    </td>
                    <td className="text-foreground px-4 py-2 text-right">{formatCost(row.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
