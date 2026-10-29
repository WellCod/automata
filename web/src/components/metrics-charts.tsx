"use client";

import { formatDuration } from "@/lib/format";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/info-hint";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import client from "@/lib/api/client";
import { LATENCY_HINTS } from "@/lib/metric-hints";
import type { components } from "@/lib/api/schema.d.ts";

type DailyMetricsPoint = components["schemas"]["DailyMetricsPoint"];

export type SeriesRange = { period: string } | { start: string; end?: string };

interface Props {
  range: SeriesRange;
  agentId?: string;
}

// Cores validadas para o fundo do card (#141414): ver DESIGN.md, seção Gráficos
const runsConfig = {
  blocked: { label: "Bloqueado", color: "var(--chart-blocked)" },
  success: { label: "Sucesso", color: "var(--chart-1)" },
  errors: { label: "Erro", color: "var(--chart-error)" },
} satisfies ChartConfig;

const latencyConfig = {
  p50: { label: "Típica (p50)", color: "var(--chart-1)" },
  p95: { label: "Pico (p95)", color: "var(--chart-2)" },
} satisfies ChartConfig;

const costConfig = {
  cost: { label: "Custo", color: "var(--chart-1)" },
} satisfies ChartConfig;

function dayLabel(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function formatUsd(v: number): string {
  return v.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 4,
  });
}

const axisProps = {
  tickLine: false,
  axisLine: false,
  tickMargin: 6,
  fontSize: 11,
} as const;

function ChartFrame({
  title,
  hints,
  children,
}: {
  title: string;
  hints?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <figure className="border-border bg-card flex flex-col gap-2 rounded border px-3 pt-2.5 pb-2">
      <figcaption className="flex items-center justify-between gap-2">
        <span className="text-foreground text-[13px] font-medium">{title}</span>
        {hints && <span className="flex items-center gap-3">{hints}</span>}
      </figcaption>
      {children}
    </figure>
  );
}

function SeriesTable({ points }: { points: DailyMetricsPoint[] }) {
  return (
    <details className="text-[13px]">
      <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-[11px]">
        Ver tabela
      </summary>
      <div className="border-border mt-2 max-h-72 overflow-auto rounded border">
        <table className="w-full">
          <thead>
            <tr className="border-border bg-card border-b">
              {["Dia", "Conversas", "Erros", "Bloqueios", "p50", "p95", "Tokens", "Custo"].map(
                (h) => (
                  <th
                    key={h}
                    className="text-muted-foreground px-3 py-1.5 text-right font-medium first:text-left"
                  >
                    {h}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.date} className="border-border border-b last:border-0">
                <td className="text-foreground px-3 py-1 text-left">{dayLabel(p.date)}</td>
                <td className="text-foreground px-3 py-1 text-right">{p.total_runs}</td>
                <td className="text-foreground px-3 py-1 text-right">{p.error_count}</td>
                <td className="text-foreground px-3 py-1 text-right">{p.blocked_count ?? 0}</td>
                <td className="text-foreground px-3 py-1 text-right">
                  {p.p50_ms === null ? "—" : formatDuration(p.p50_ms)}
                </td>
                <td className="text-foreground px-3 py-1 text-right">
                  {p.p95_ms === null ? "—" : formatDuration(p.p95_ms)}
                </td>
                <td className="text-foreground px-3 py-1 text-right">{p.total_tokens}</td>
                <td className="text-foreground px-3 py-1 text-right">
                  {p.total_cost === null ? "—" : formatUsd(p.total_cost)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function MetricsCharts({ range, agentId }: Props) {
  const query = { ...range, agent_id: agentId };
  const { data, isPending, isError, refetch } = useQuery<DailyMetricsPoint[]>({
    queryKey: ["metrics:timeseries", query],
    queryFn: async () => {
      const res = await client.GET("/api/v1/metrics/timeseries", { params: { query } });
      if (res.error) throw new Error("Falha ao carregar série");
      return res.data!;
    },
  });

  if (isPending) {
    return (
      <div className="@container" aria-busy="true">
        <div className="grid grid-cols-1 gap-3 @5xl:grid-cols-3">
          <span className="sr-only">Carregando gráficos…</span>
          {[0, 1, 2].map((i) => (
            <div key={i} className="border-border bg-card h-56 animate-pulse rounded border" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="border-destructive/30 text-destructive flex items-center justify-between gap-3 rounded border px-4 py-3 text-[13px]">
        <span>Erro ao carregar os gráficos.</span>
        <Button size="sm" onClick={() => void refetch()}>
          Tentar de novo
        </Button>
      </div>
    );
  }

  if (!data.some((p) => p.total_runs > 0 || p.total_tokens > 0)) {
    return <p className="text-muted-foreground text-[13px]">Nenhuma execução no período.</p>;
  }

  const rows = data.map((p) => ({
    date: p.date,
    success: p.total_runs - p.error_count - (p.blocked_count ?? 0),
    blocked: p.blocked_count ?? 0,
    errors: p.error_count,
    p50: p.p50_ms,
    p95: p.p95_ms,
    cost: p.total_cost ?? 0,
  }));

  return (
    <div className="@container flex flex-col gap-2">
      <div className="grid grid-cols-1 gap-3 @5xl:grid-cols-3">
        <ChartFrame title="Conversas por dia">
          <ChartContainer config={runsConfig} className="aspect-auto h-48 w-full">
            <BarChart data={rows} barCategoryGap={2}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={16} {...axisProps} />
              <YAxis allowDecimals={false} width={32} {...axisProps} />
              <ChartTooltip
                cursor={false}
                content={<ChartTooltipContent labelFormatter={(v) => dayLabel(String(v))} />}
              />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar
                isAnimationActive={false}
                dataKey="blocked"
                stackId="runs"
                fill="var(--color-blocked)"
              />
              <Bar
                isAnimationActive={false}
                dataKey="success"
                stackId="runs"
                fill="var(--color-success)"
              />
              <Bar
                isAnimationActive={false}
                dataKey="errors"
                stackId="runs"
                fill="var(--color-errors)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ChartContainer>
        </ChartFrame>

        <ChartFrame
          title="Tempo de resposta"
          hints={
            <>
              <InfoHint label="p50" ariaLabel="O que é p50">
                {LATENCY_HINTS.p50}
              </InfoHint>
              <InfoHint label="p95" ariaLabel="O que é p95">
                {LATENCY_HINTS.p95}
              </InfoHint>
            </>
          }
        >
          <ChartContainer config={latencyConfig} className="aspect-auto h-48 w-full">
            <LineChart data={rows}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={16} {...axisProps} />
              <YAxis width={52} tickFormatter={(v: number) => formatDuration(v)} {...axisProps} />
              <ChartTooltip
                content={
                  <ChartTooltipContent
                    labelFormatter={(v) => dayLabel(String(v))}
                    formatter={(value, name) => (
                      <span className="flex w-full justify-between gap-3">
                        <span className="text-muted-foreground">
                          {latencyConfig[name as keyof typeof latencyConfig]?.label ?? name}
                        </span>
                        <span className="text-foreground font-medium">
                          {formatDuration(Number(value))}
                        </span>
                      </span>
                    )}
                  />
                }
              />
              <ChartLegend content={<ChartLegendContent />} />
              <Line
                isAnimationActive={false}
                dataKey="p50"
                stroke="var(--color-p50)"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              <Line
                isAnimationActive={false}
                dataKey="p95"
                stroke="var(--color-p95)"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            </LineChart>
          </ChartContainer>
        </ChartFrame>

        <ChartFrame title="Custo estimado por dia">
          <ChartContainer config={costConfig} className="aspect-auto h-48 w-full">
            <BarChart data={rows} barCategoryGap={2}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={16} {...axisProps} />
              <YAxis width={48} tickFormatter={(v: number) => `$${v}`} {...axisProps} />
              <ChartTooltip
                cursor={false}
                content={
                  <ChartTooltipContent
                    hideIndicator
                    labelFormatter={(v) => dayLabel(String(v))}
                    formatter={(value) => (
                      <span className="text-foreground font-medium">
                        {formatUsd(Number(value))}
                      </span>
                    )}
                  />
                }
              />
              <Bar
                isAnimationActive={false}
                dataKey="cost"
                fill="var(--color-cost)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ChartContainer>
        </ChartFrame>
      </div>
      <SeriesTable points={data} />
    </div>
  );
}
