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
  draft: "text-amber-400",
  published: "text-accent",
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
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-[13px] font-medium">Versões</h2>
        {draft && (
          <button
            type="button"
            onClick={() => publishMutation.mutate()}
            disabled={publishMutation.isPending}
            className="border-accent text-accent hover:border-accent/70 hover:text-accent/70 inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
          >
            {publishMutation.isPending ? "Publicando…" : "Publicar"}
          </button>
        )}
      </div>

      {publishMutation.isError && (
        <p className="text-destructive text-[11px]">Erro ao publicar. Tente novamente.</p>
      )}
      {rollbackMutation.isError && (
        <p className="text-destructive text-[11px]">Erro ao reverter. Tente novamente.</p>
      )}

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && <p className="text-destructive text-[13px]">Erro ao carregar versões.</p>}

      {!isPending && !isError && versions && versions.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhuma versão salva.</p>
      )}

      {!isPending && !isError && versions && versions.length > 0 && (
        <ul className="flex flex-col gap-1">
          {versions.map((v) => {
            const diffs =
              v.status === "draft" && current ? diffPayload(current.payload, v.payload) : [];

            return (
              <li
                key={v.id}
                className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-foreground text-[13px] font-medium">
                      v{v.version_number}
                    </span>
                    <span
                      className={`text-[11px] font-medium ${STATUS_CLS[v.status] ?? "text-muted-foreground"}`}
                    >
                      {STATUS_LABELS[v.status] ?? v.status}
                    </span>
                    <span className="text-muted-foreground text-[11px]">{v.author}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-[11px]">
                      {new Date(v.created_at).toLocaleDateString("pt-BR")}
                    </span>
                    {v.status === "published" && v.id !== current?.id && (
                      <button
                        type="button"
                        onClick={() => rollbackMutation.mutate(v.id)}
                        disabled={rollbackMutation.isPending}
                        className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground inline-flex h-5 items-center rounded border px-1.5 text-[10px] transition-colors disabled:opacity-40"
                      >
                        Reverter
                      </button>
                    )}
                  </div>
                </div>
                {diffs.length > 0 && (
                  <p className="text-muted-foreground text-[11px]">Alterado: {diffs.join(", ")}</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
