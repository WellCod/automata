"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Ban,
  CheckCircle2,
  ChevronRight,
  ListChecks,
  PauseCircle,
  ShieldAlert,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { ReviewHistory } from "@/components/review-history";
import { RunTrace } from "@/components/run-trace";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { blockLabel, screenedText, stopLabel } from "@/lib/guardrail-labels";
import type { components } from "@/lib/api/schema.d.ts";

type AgentRunResponse = components["schemas"]["AgentRunResponse"];

interface Props {
  agentId: string;
  // agente e time: abre a aba de testes com o caso montado a partir do run
  onMakeCase?: (runId: string) => void;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  success: <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-600 dark:text-green-500" />,
  error: <XCircle className="text-destructive h-3.5 w-3.5 shrink-0" />,
  paused: <PauseCircle className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-400" />,
  cancelled: <Ban className="text-muted-foreground h-3.5 w-3.5 shrink-0" />,
  blocked: <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />,
};

const STATUS_LABEL: Record<string, string> = {
  success: "Sucesso",
  error: "Erro",
  paused: "Aguardando confirmação",
  cancelled: "Cancelado",
  blocked: "Bloqueado",
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

// run de workflow: o consumo é a soma das etapas, gravadas nos agentes e times
export function workflowUsage(run: AgentRunResponse): string {
  const steps = run.steps ?? 0;
  const parts = [`${steps} etapa${steps === 1 ? "" : "s"}`];
  parts.push(`${(run.total_tokens ?? 0).toLocaleString("pt-BR")} tokens`);
  if (run.cost != null) {
    parts.push(
      run.cost.toLocaleString("pt-BR", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 4,
      }),
    );
  }
  return parts.join(" · ");
}

function RunItem({
  run,
  onMakeCase,
}: {
  run: AgentRunResponse;
  onMakeCase?: (runId: string) => void;
}) {
  const icon = STATUS_ICON[run.status] ?? (
    <Activity className="text-muted-foreground h-3.5 w-3.5 shrink-0" />
  );
  const [open, setOpen] = useState(false);
  return (
    <li className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
      <button
        type="button"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        disabled={!run.run_id}
        aria-expanded={open}
        className="flex min-h-8 w-full items-center justify-between gap-2 text-left disabled:cursor-default"
      >
        <div className="flex items-center gap-1.5">
          {run.run_id && (
            <ChevronRight
              className={`text-muted-foreground h-3 w-3 transition-transform ${open ? "rotate-90" : ""}`}
              aria-hidden
            />
          )}
          {icon}
          <span className="text-foreground text-[13px] font-medium">
            {STATUS_LABEL[run.status] ?? run.status}
          </span>
          {run.status === "blocked" && (
            <span className="text-[11px] text-amber-400">{blockLabel(run.blocked_by)}</span>
          )}
          {run.stop_reason && (
            <span className="text-[11px] text-amber-600 dark:text-amber-400">
              {stopLabel(run.stop_reason)}
            </span>
          )}
          <span className="text-muted-foreground text-[11px]">{run.user_id}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-[11px]">
            {formatDuration(run.duration_ms)}
          </span>
          <span className="text-muted-foreground text-[11px]">{formatDate(run.created_at)}</span>
        </div>
      </button>
      {(run.screened_tools ?? []).length > 0 && (
        <p
          className="text-[11px] text-amber-600 dark:text-amber-400"
          aria-label="Resultados retirados"
        >
          {screenedText(run.screened_tools ?? [])}
        </p>
      )}
      {run.steps != null && (
        <p className="text-muted-foreground text-[11px]" aria-label="Consumo das etapas">
          {workflowUsage(run)}
        </p>
      )}
      {run.error && (
        <p
          title={run.error}
          className={`text-muted-foreground mt-0.5 font-mono text-[11px] ${open ? "whitespace-pre-wrap" : "truncate"}`}
        >
          {run.error}
        </p>
      )}
      {open && run.run_id && (
        <div className="border-border mt-1 flex flex-col gap-2 border-t pt-2">
          {/* bloqueio por guardrail e etapa de workflow não viram caso (a API recusa) */}
          {onMakeCase && run.status !== "blocked" && run.steps == null && (
            <div>
              <Button size="xs" variant="muted" onClick={() => onMakeCase(run.run_id!)}>
                <ListChecks aria-hidden />
                Virar caso de teste
              </Button>
            </div>
          )}
          <ReviewHistory runId={run.run_id} />
          <RunTrace runId={run.run_id} />
        </div>
      )}
    </li>
  );
}

const PAGE_SIZE = 25;
type RunStatus = "" | "success" | "error" | "blocked" | "paused" | "cancelled";
const FILTER_LABEL: Record<Exclude<RunStatus, "">, string> = {
  success: "Sucesso",
  error: "Erro",
  blocked: "Bloqueadas",
  paused: "Aguardando aprovação",
  cancelled: "Canceladas",
};
const PERIODS = { "": "Todo o período", "1": "Último dia", "7": "7 dias", "30": "30 dias" };

export function RunsPanel({ agentId, onMakeCase }: Props) {
  // filtro e páginas: com milhares de execuções a lista era só o fim (UX-07)
  const [status, setStatus] = useState<RunStatus>("");
  const [days, setDays] = useState<keyof typeof PERIODS>("");
  const [page, setPage] = useState(1);
  const { data, isPending, isError } = useQuery({
    queryKey: ["runs", agentId, status, days, page],
    queryFn: async () => {
      const since = days
        ? new Date(Date.now() - Number(days) * 86_400_000).toISOString()
        : undefined;
      const result = await client.GET("/api/v1/configs/{config_id}/runs", {
        params: {
          path: { config_id: agentId },
          query: { page, page_size: PAGE_SIZE, status: status || undefined, since },
        },
      });
      if (result.error) throw new Error("Falha ao carregar execuções");
      return result.data!;
    },
    refetchInterval: 5_000,
  });

  const filters = (
    <div className="flex flex-wrap gap-2">
      <select
        aria-label="Filtrar por status"
        value={status}
        onChange={(e) => {
          setStatus(e.target.value as RunStatus);
          setPage(1);
        }}
        className="border-border text-foreground rounded border bg-[var(--input)] px-2 py-1 text-[12px]"
      >
        <option value="">Todos os status</option>
        {Object.entries(FILTER_LABEL).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <select
        aria-label="Filtrar por período"
        value={days}
        onChange={(e) => {
          setDays(e.target.value as keyof typeof PERIODS);
          setPage(1);
        }}
        className="border-border text-foreground rounded border bg-[var(--input)] px-2 py-1 text-[12px]"
      >
        {Object.entries(PERIODS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
    </div>
  );

  if (isPending) return <p className="text-muted-foreground text-[13px]">Carregando…</p>;
  if (isError) return <p className="text-destructive text-[13px]">Falha ao carregar execuções.</p>;

  if (data.items.length === 0)
    return (
      <div className="flex flex-col gap-3">
        {filters}
        <p className="text-muted-foreground text-[13px]">
          {status || days ? "Nenhuma execução com esse filtro." : "Nenhuma execução registrada."}
        </p>
      </div>
    );

  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  return (
    <div className="flex flex-col gap-3">
      {filters}
      <p className="text-muted-foreground text-[11px]">
        {data.total} execução{data.total !== 1 ? "ões" : ""} · atualiza a cada 5s
      </p>
      <ul className="flex flex-col gap-1">
        {data.items.map((run) => (
          <RunItem key={run.id} run={run} onMakeCase={onMakeCase} />
        ))}
      </ul>
      {pages > 1 && (
        <div className="text-muted-foreground flex items-center justify-end gap-2 text-[12px]">
          <button
            type="button"
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page === 1}
            className="hover:text-foreground disabled:opacity-40"
          >
            Anterior
          </button>
          <span>
            {page} de {pages}
          </span>
          <button
            type="button"
            onClick={() => setPage((current) => Math.min(pages, current + 1))}
            disabled={page >= pages}
            className="hover:text-foreground disabled:opacity-40"
          >
            Próxima
          </button>
        </div>
      )}
    </div>
  );
}
