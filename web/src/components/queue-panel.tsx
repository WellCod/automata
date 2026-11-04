"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

type QueueJob = components["schemas"]["QueueJob"];

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: "Na fila",
  running: "Rodando",
  completed: "Concluído",
  failed: "Falhou",
  cancelled: "Cancelado",
  paused: "Pausado",
};

const KEY = ["queue"];

function when(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString("pt-BR") : "—";
}

export function QueuePanel() {
  const queryClient = useQueryClient();
  const { data, error, isLoading } = useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const res = await client.GET("/api/v1/queue");
      if (res.error) throw new Error("Falha ao carregar a fila. Apenas owners têm acesso.");
      return res.data;
    },
    refetchInterval: 5000,
  });
  const requeue = useMutation({
    mutationFn: async (job: QueueJob) => {
      const res = await client.POST("/api/v1/queue/jobs/{job_id}/requeue", {
        params: { path: { job_id: job.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao recolocar na fila"));
    },
    onSuccess: () => {
      toast.success("Job de volta na fila");
      void queryClient.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(e.message),
  });

  if (isLoading) return <p className="text-muted-foreground text-[13px]">Carregando…</p>;
  if (error) return <p className="text-destructive text-[13px]">{error.message}</p>;
  if (!data) return null;
  if (!data.durable)
    return (
      <p role="status" className="text-muted-foreground text-[13px]">
        A fila durável está desligada (BACKGROUND_QUEUE_DURABLE=false): os runs em background rodam
        em memória e não aparecem aqui.
      </p>
    );

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {Object.entries(JOB_STATUS_LABELS).map(([status, label]) => (
          <div key={status} className="border-border rounded border px-3 py-2">
            <dt className="text-muted-foreground text-[11px]">{label}</dt>
            <dd
              className={`text-[18px] font-medium tabular-nums ${status === "failed" && data.counts[status] ? "text-destructive" : "text-foreground"}`}
            >
              {(data.counts[status] ?? 0).toLocaleString("pt-BR")}
            </dd>
          </div>
        ))}
      </dl>
      {data.oldest_queued_at && (
        <p className="text-muted-foreground text-[12px]">
          Na fila desde {when(data.oldest_queued_at)}
        </p>
      )}
      {data.jobs.length === 0 ? (
        <p className="text-muted-foreground text-[13px]">Nenhum job ainda.</p>
      ) : (
        <div className="max-w-full min-w-0 overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead className="text-muted-foreground text-[12px]">
              <tr>
                <th className="py-1.5 pr-3 font-normal">Agente ou time</th>
                <th className="py-1.5 pr-3 font-normal">Situação</th>
                <th className="py-1.5 pr-3 font-normal">Tentativa</th>
                <th className="hidden py-1.5 pr-3 font-normal sm:table-cell">Criado</th>
                <th className="py-1.5 font-normal">
                  <span className="sr-only">Ações</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.jobs.map((job) => (
                <tr key={job.id} className="border-border border-t align-top">
                  <td className="py-1.5 pr-3">
                    {job.component_name ?? job.component_id}
                    <span className="text-muted-foreground block text-[11px]">
                      {job.component_type}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3">
                    {JOB_STATUS_LABELS[job.status ?? ""] ?? job.status}
                    {job.error && (
                      <span className="text-destructive block text-[11px] break-all">
                        {job.error}
                      </span>
                    )}
                  </td>
                  <td className="py-1.5 pr-3 tabular-nums">{job.attempt}</td>
                  <td className="hidden py-1.5 pr-3 sm:table-cell">{when(job.created_at)}</td>
                  <td className="py-1.5">
                    {(job.status === "failed" || job.status === "cancelled") && (
                      <Button
                        size="xs"
                        variant="muted"
                        disabled={requeue.isPending}
                        onClick={() => requeue.mutate(job)}
                      >
                        Repetir
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
