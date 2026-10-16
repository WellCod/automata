"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/status-badge";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfigVersionDetail = components["schemas"]["AgentConfigVersionDetail"];
type ConfigPayload = components["schemas"]["ConfigPayload"];

interface Props {
  agentId: string;
  // versão em produção vem do detalhe do agente: depois de um rollback ela não é a publicada mais recente
  currentVersionId?: string | null;
  hasUnsavedChanges?: boolean;
}

type Pending = { kind: "publish" } | { kind: "rollback"; versionId: string; versionNumber: number };

const STATUS_LABELS: Record<string, string> = {
  draft: "Rascunho",
  published: "Publicado",
};

const STATUS_CLS: Record<string, string> = {
  draft: "text-amber-600 dark:text-amber-400",
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

export function VersionsPanel({ agentId, currentVersionId, hasUnsavedChanges = false }: Props) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(null);

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
    onError: () => toast.error("Erro ao publicar. Tente novamente."),
    onSuccess: (v) => {
      toast.success(`v${v.version_number} publicada`);
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
    onError: () => toast.error("Erro ao reverter. Tente novamente."),
    onSuccess: (v) => {
      toast.success(`v${v.version_number} ativa de novo`);
      void queryClient.invalidateQueries({ queryKey: ["versions", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["config", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
    },
  });

  const draft = versions?.find((v) => v.status === "draft");
  const current = versions?.find((v) => v.id === currentVersionId);
  const busy = publishMutation.isPending || rollbackMutation.isPending;

  function confirm() {
    if (!pending) return;
    if (pending.kind === "publish") publishMutation.mutate();
    else rollbackMutation.mutate(pending.versionId);
    setPending(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-[13px] font-medium">Versões</h2>
        {draft && (
          <Button
            variant="accent"
            size="sm"
            onClick={() => setPending({ kind: "publish" })}
            disabled={busy || pending !== null}
          >
            {publishMutation.isPending ? "Publicando…" : "Publicar"}
          </Button>
        )}
      </div>

      {pending && (
        <div
          role="alertdialog"
          aria-label="Confirmar"
          className="border-border bg-card flex flex-col gap-2 rounded border px-3 py-2"
        >
          <p className="text-foreground text-[13px]">
            {pending.kind === "publish"
              ? "Publicar o rascunho? A nova versão passa a responder em produção."
              : `Reverter para v${pending.versionNumber}? Ela volta a responder em produção.`}
          </p>
          {pending.kind === "publish" && hasUnsavedChanges && (
            <p className="text-[11px] text-amber-600 dark:text-amber-400">
              Há alterações não salvas no formulário. Elas não entram na publicação.
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button size="sm" onClick={() => setPending(null)}>
              Cancelar
            </Button>
            <Button variant="accent" size="sm" onClick={confirm}>
              {pending.kind === "publish" ? "Confirmar publicação" : "Confirmar reversão"}
            </Button>
          </div>
        </div>
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
                    {v.id === currentVersionId && <Badge tone="active">Ativa</Badge>}
                    {v.status === "published" && v.id !== currentVersionId && (
                      <Button
                        size="xs"
                        onClick={() =>
                          setPending({
                            kind: "rollback",
                            versionId: v.id,
                            versionNumber: v.version_number,
                          })
                        }
                        disabled={busy || pending !== null}
                      >
                        Reverter
                      </Button>
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
