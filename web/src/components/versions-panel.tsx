"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfigVersionDetail = components["schemas"]["AgentConfigVersionDetail"];
type ConfigPayload = components["schemas"]["ConfigPayload"];

interface Props {
  agentId: string;
}

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  published: "Publicado",
};

const STATUS_CLS: Record<string, string> = {
  draft: "bg-amber-100 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400",
  published: "bg-green-100 text-green-700 dark:bg-green-950/40 dark:text-green-400",
};

function diffPayload(a: ConfigPayload, b: ConfigPayload): string[] {
  const diffs: string[] = [];
  if (a.model_id !== b.model_id) diffs.push(`modelo: ${a.model_id} → ${b.model_id}`);
  const instrKeys = ["persona", "situation", "tone", "objective", "guardrails"] as const;
  for (const k of instrKeys) {
    if ((a.instructions?.[k] ?? "") !== (b.instructions?.[k] ?? "")) diffs.push(`instruções.${k}`);
  }
  const capKeys = ["extended_thinking", "structured_output", "vision"] as const;
  for (const k of capKeys) {
    if ((a.capabilities?.[k] ?? false) !== (b.capabilities?.[k] ?? false)) {
      diffs.push(`capabilities.${k}`);
    }
  }
  return diffs;
}

export function VersionsPanel({ agentId }: Props) {
  const queryClient = useQueryClient();

  const {
    data: versions,
    isPending,
    isError,
  } = useQuery<AgentConfigVersionDetail[]>({
    queryKey: ["versions", agentId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/versions", {
        params: { path: { config_id: agentId } },
      });
      if (res.error) throw new Error("Falha ao carregar versões");
      return res.data!;
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/configs/{config_id}/publish", {
        params: { path: { config_id: agentId } },
      });
      if (res.error) throw new Error("Falha ao publicar");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["versions", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["config", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async (versionId: string) => {
      const res = await client.POST("/api/v1/configs/{config_id}/rollback", {
        params: { path: { config_id: agentId } },
        body: { version_id: versionId },
      });
      if (res.error) throw new Error("Falha ao reverter");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["versions", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["config", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  const draft = versions?.find((v) => v.status === "draft");
  const published = versions?.filter((v) => v.status === "published") ?? [];
  const current = published[0];

  return (
    <div className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-700">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Versões</h2>
        {draft && (
          <button
            type="button"
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition-colors hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            {publishMutation.isPending ? "Publicando…" : "Publicar rascunho"}
          </button>
        )}
      </div>

      {publishMutation.isError && (
        <p className="mt-2 text-xs text-red-500 dark:text-red-400">
          Erro ao publicar. Tente novamente.
        </p>
      )}
      {rollbackMutation.isError && (
        <p className="mt-2 text-xs text-red-500 dark:text-red-400">
          Erro ao reverter. Tente novamente.
        </p>
      )}

      {isPending && <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-600">Carregando…</p>}
      {isError && (
        <p className="mt-3 text-xs text-red-500 dark:text-red-400">Erro ao carregar versões.</p>
      )}

      {!isPending && !isError && versions && versions.length === 0 && (
        <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-600">Nenhuma versão salva.</p>
      )}

      {!isPending && !isError && versions && versions.length > 0 && (
        <ul className="mt-3 flex flex-col gap-2">
          {versions.map((v) => {
            const diffs =
              v.status === "draft" && current ? diffPayload(current.payload, v.payload) : [];

            return (
              <li
                key={v.id}
                className="flex flex-col gap-1 rounded-lg border border-zinc-100 bg-zinc-50 px-3 py-2 transition-colors dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      v{v.version_number}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_CLS[v.status] ?? ""}`}
                    >
                      {STATUS_LABELS[v.status] ?? v.status}
                    </span>
                    <span className="text-xs text-zinc-400 dark:text-zinc-600">{v.author}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-zinc-400 dark:text-zinc-600">
                      {new Date(v.created_at).toLocaleDateString("pt-BR")}
                    </span>
                    {v.status === "published" && v.id !== current?.id && (
                      <button
                        type="button"
                        onClick={() => rollbackMutation.mutate(v.id)}
                        disabled={rollbackMutation.isPending}
                        className="rounded-md border border-zinc-200 px-2 py-0.5 text-xs text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
                      >
                        Reverter
                      </button>
                    )}
                  </div>
                </div>
                {diffs.length > 0 && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    Alterado: {diffs.join(", ")}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
