"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, XCircle } from "lucide-react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type AgentRunResponse = components["schemas"]["AgentRunResponse"];

interface Props {
  agentId: string;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-500" />,
  error: <XCircle className="h-3.5 w-3.5 shrink-0 text-red-400" />,
};

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function RunItem({ run }: { run: AgentRunResponse }) {
  const icon = STATUS_ICON[run.status] ?? (
    <Activity className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
  );
  return (
    <li className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          {icon}
          <span className="text-foreground text-[13px] font-medium capitalize">{run.status}</span>
          <span className="text-muted-foreground text-[11px]">{run.user_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-[11px]">
            {formatDuration(run.duration_ms)}
          </span>
          <span className="text-muted-foreground text-[11px]">{formatDate(run.created_at)}</span>
        </div>
      </div>
      {run.error && (
        <p className="text-muted-foreground mt-0.5 truncate font-mono text-[11px]">{run.error}</p>
      )}
    </li>
  );
}

export function RunsPanel({ agentId }: Props) {
  const { data, isPending, isError } = useQuery({
    queryKey: ["runs", agentId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/runs", {
        params: { path: { config_id: agentId } },
      });
      if (res.error) throw new Error("Falha ao carregar execuções");
      return res.data!;
    },
    refetchInterval: 5_000,
  });

  if (isPending) return <p className="text-muted-foreground text-[13px]">Carregando…</p>;
  if (isError) return <p className="text-[13px] text-red-400">Falha ao carregar execuções.</p>;

  if (data.items.length === 0)
    return <p className="text-muted-foreground text-[13px]">Nenhuma execução registrada.</p>;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-[11px]">
        {data.total} execução{data.total !== 1 ? "ões" : ""} · atualiza a cada 5s
      </p>
      <ul className="flex flex-col gap-1">
        {data.items.map((run) => (
          <RunItem key={run.id} run={run} />
        ))}
      </ul>
    </div>
  );
}
