"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type SubjectInventory = components["schemas"]["SubjectInventory"];
export type DataSubjectRequest = components["schemas"]["DataSubjectRequestResponse"];

export const COUNT_LABELS: Record<string, string> = {
  sessions: "Conversas",
  runs: "Runs da conversa",
  memories: "Memórias",
  approvals: "Aprovações",
  tool_results: "Resultados de tool",
  traces: "Traces",
  spans: "Spans",
  transcripts: "Transcrições",
  compactions: "Compactações",
  jobs: "Jobs da fila",
  eval_runs: "Runs de suíte",
  learnings: "Aprendizados",
  metrics: "Métricas do Agno",
  agent_runs: "Runs registrados",
  usage_events: "Eventos de consumo",
  usage_periods: "Meses de consumo",
  eval_cases_unlinked: "Casos de teste desligados",
  caller_budget: "Orçamento por quem chama",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Na fila",
  running: "Rodando",
  done: "Pronto",
  failed: "Falhou",
  expired: "Arquivo vencido",
};

const REQUESTS = ["data-subject-requests"];
const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function when(value: string | null): string {
  return value ? new Date(value).toLocaleString("pt-BR") : "—";
}

export function useDataSubjectRequests() {
  return useQuery({
    queryKey: REQUESTS,
    queryFn: async () => {
      const res = await client.GET("/api/v1/data-subject-requests");
      if (res.error) throw new Error("Falha ao carregar os pedidos. Apenas owners têm acesso.");
      return res.data;
    },
    // pedido em background: atualiza até terminar
    refetchInterval: (query) =>
      query.state.data?.some((r) => r.status === "pending" || r.status === "running")
        ? 2000
        : false,
  });
}

export function InventoryView({ inventory }: { inventory: SubjectInventory }) {
  if (inventory.total === 0)
    return (
      <p role="status" className="text-muted-foreground text-[13px]">
        Nada guardado para {inventory.user_id}.
      </p>
    );
  const rows = Object.entries(inventory.counts).filter(([, n]) => n > 0);
  return (
    <dl className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
      {rows.map(([key, n]) => (
        <div key={key} className="flex items-baseline justify-between gap-4 py-1 text-[13px]">
          <dt className="text-muted-foreground">{COUNT_LABELS[key] ?? key}</dt>
          <dd className="text-foreground tabular-nums">{n.toLocaleString("pt-BR")}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SubjectActions({ userId, onDone }: { userId: string; onDone: () => void }) {
  const id = useId();
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [typed, setTyped] = useState("");

  const exportData = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/data-subjects/{user_id}/export", {
        params: { path: { user_id: userId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao pedir a exportação"));
    },
    onSuccess: () => {
      toast.success("Exportação pedida. O arquivo aparece nos pedidos abaixo.");
      void queryClient.invalidateQueries({ queryKey: REQUESTS });
    },
    onError: (e) => toast.error(e.message),
  });

  const erase = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/data-subjects/{user_id}/erase", {
        params: { path: { user_id: userId } },
        body: { confirm: typed },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao pedir a exclusão"));
    },
    onSuccess: () => {
      toast.success("Exclusão pedida.");
      setConfirming(false);
      setTyped("");
      void queryClient.invalidateQueries({ queryKey: REQUESTS });
      onDone();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => exportData.mutate()} disabled={exportData.isPending}>
          Exportar os dados
        </Button>
        {!confirming && (
          <Button variant="subtleDestructive" onClick={() => setConfirming(true)}>
            Apagar os dados
          </Button>
        )}
      </div>
      {confirming && (
        <div className="border-destructive/40 flex flex-col gap-2 rounded border px-4 py-3">
          <p className="text-foreground text-[13px]">
            Apaga as conversas, memórias, aprovações e traces desta pessoa. No consumo e nos runs
            registrados, o id vira um pseudônimo. Não tem volta e não alcança backups.
          </p>
          <label htmlFor={`${id}-confirm`} className="text-muted-foreground text-[12px]">
            Digite {userId} para confirmar
          </label>
          <input
            id={`${id}-confirm`}
            className={inputCls}
            value={typed}
            autoComplete="off"
            onChange={(e) => setTyped(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              variant="destructive"
              disabled={typed !== userId || erase.isPending}
              onClick={() => erase.mutate()}
            >
              Apagar definitivamente
            </Button>
            <Button
              variant="muted"
              onClick={() => {
                setConfirming(false);
                setTyped("");
              }}
            >
              Cancelar
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function requestTotal(r: DataSubjectRequest): number {
  return Object.values(r.counts ?? {}).reduce<number>(
    (sum, n) => sum + (typeof n === "number" ? n : 0),
    0,
  );
}

export function RequestsTable({ requests }: { requests: DataSubjectRequest[] }) {
  if (requests.length === 0)
    return <p className="text-muted-foreground text-[13px]">Nenhum pedido ainda.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[13px]">
        <thead className="text-muted-foreground text-[12px]">
          <tr>
            <th className="py-1.5 pr-3 font-normal">Pedido</th>
            <th className="py-1.5 pr-3 font-normal">Titular</th>
            <th className="py-1.5 pr-3 font-normal">Situação</th>
            <th className="py-1.5 pr-3 font-normal">Quem pediu</th>
            <th className="py-1.5 pr-3 font-normal">Quando</th>
            <th className="py-1.5 font-normal">
              <span className="sr-only">Arquivo</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {requests.map((r) => (
            <tr key={r.id} className="border-border border-t align-top">
              <td className="py-1.5 pr-3">{r.kind === "erase" ? "Exclusão" : "Exportação"}</td>
              <td className="py-1.5 pr-3">
                {r.subject ?? (
                  <span
                    className="text-muted-foreground font-mono text-[12px]"
                    title={r.subject_hash}
                  >
                    hash {r.subject_hash.slice(0, 12)}
                  </span>
                )}
              </td>
              <td className="py-1.5 pr-3">
                {STATUS_LABELS[r.status] ?? r.status}
                {r.status === "done" && r.counts && (
                  <span className="text-muted-foreground">
                    {" "}
                    · {requestTotal(r).toLocaleString("pt-BR")} linhas
                  </span>
                )}
                {r.error && <span className="text-destructive block text-[12px]">{r.error}</span>}
              </td>
              <td className="py-1.5 pr-3">{r.requested_by}</td>
              <td className="py-1.5 pr-3">{when(r.created_at)}</td>
              <td className="py-1.5">
                {r.kind === "export" && r.status === "done" && (
                  <a
                    className="text-accent underline"
                    href={`/api/api/v1/data-subject-requests/${r.id}/download`}
                    title={`Vale até ${when(r.expires_at)}`}
                  >
                    Baixar
                  </a>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DataSubjectsPanel() {
  const id = useId();
  const [query, setQuery] = useState("");
  const [userId, setUserId] = useState<string | null>(null);
  const inventory = useQuery({
    queryKey: ["data-subject", userId],
    enabled: userId !== null,
    queryFn: async () => {
      const res = await client.GET("/api/v1/data-subjects/{user_id}", {
        params: { path: { user_id: userId ?? "" } },
      });
      if (res.error) throw new Error("Falha ao consultar o titular. Apenas owners têm acesso.");
      return res.data;
    },
  });
  const requests = useDataSubjectRequests();

  return (
    <div className="flex flex-col gap-4">
      <form
        className="flex flex-col gap-1.5"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) setUserId(query.trim());
        }}
      >
        <label htmlFor={`${id}-user`} className="text-foreground text-[13px]">
          Id do titular
        </label>
        <div className="flex gap-2">
          <input
            id={`${id}-user`}
            className={inputCls}
            value={query}
            placeholder="ana@cliente.com"
            autoComplete="off"
            onChange={(e) => setQuery(e.target.value)}
          />
          <Button type="submit" variant="strong" disabled={!query.trim()}>
            Consultar
          </Button>
        </div>
      </form>

      {userId !== null && (
        <section
          aria-labelledby={`${id}-found`}
          className="border-border flex flex-col gap-3 rounded border px-4 py-3"
        >
          <h2 id={`${id}-found`} className="text-foreground text-sm font-medium break-all">
            {userId}
          </h2>
          {inventory.isLoading && <p className="text-muted-foreground text-[13px]">Consultando…</p>}
          {inventory.error && (
            <p className="text-destructive text-[13px]">{inventory.error.message}</p>
          )}
          {inventory.data && <InventoryView inventory={inventory.data} />}
          {inventory.data && inventory.data.total > 0 && (
            <SubjectActions userId={userId} onDone={() => void inventory.refetch()} />
          )}
        </section>
      )}

      <section aria-labelledby={`${id}-requests`} className="flex flex-col gap-2">
        <h2 id={`${id}-requests`} className="text-foreground text-sm font-medium">
          Pedidos
        </h2>
        <p className="text-muted-foreground text-[12px]">
          O arquivo exportado fica 7 dias e depois sai do banco junto com o id em claro. A exclusão
          nunca guarda o id, só o hash.
        </p>
        {requests.error && <p className="text-destructive text-[13px]">{requests.error.message}</p>}
        {requests.data && <RequestsTable requests={requests.data} />}
      </section>
    </div>
  );
}
