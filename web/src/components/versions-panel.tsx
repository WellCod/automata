"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { AuditLog } from "@/components/audit-log";
import { CanaryPanel, useCanary } from "@/components/canary-panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/status-badge";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { useEvalCases, useEvalSettings } from "@/lib/api/evals";
import { useMe } from "@/lib/api/users";
import { type EvalSettings, runActive } from "@/lib/eval-checks";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfigVersionDetail = components["schemas"]["AgentConfigVersionDetail"];
type ConfigPayload = components["schemas"]["ConfigPayload"];

interface Props {
  agentId: string;
  // versão em produção vem do detalhe do agente: depois de um rollback ela não é a publicada mais recente
  currentVersionId?: string | null;
  // rascunho de verdade do config: versões antigas seguem com status draft depois de publicadas
  draftVersionId?: string | null;
  hasUnsavedChanges?: boolean;
  // agente e time têm suíte de testes (ADR-0015); workflow ainda não
  suite?: boolean;
  // liberação gradual (ADR-0040): agente e time
  canary?: boolean;
}

function OwnerHistory({ configId }: { configId: string }) {
  const { data: me } = useMe();
  if (me?.role !== "owner") return null;
  return (
    <section aria-label="Histórico de ações" className="flex flex-col gap-1 pt-2">
      <h3 className="text-foreground text-[13px] font-medium">Histórico de ações</h3>
      <AuditLog configId={configId} />
    </section>
  );
}

function SuiteStatus({ settings, cases }: { settings: EvalSettings | undefined; cases: number }) {
  if (!settings || (cases === 0 && !settings.require_passing_evals)) return null;
  const blocked = settings.require_passing_evals && !settings.can_publish;
  const run = settings.draft_run;
  let text = "A suíte ainda não rodou no rascunho atual.";
  if (run && runActive(run)) text = "A suíte está rodando no rascunho atual…";
  else if (run?.status === "failed") text = "A última execução da suíte no rascunho falhou.";
  else if (run) text = `Suíte no rascunho: ${run.passed} de ${run.total} passaram.`;
  const green = run?.status === "completed" && run.passed === run.total && run.total > 0;
  return (
    <div
      role="status"
      aria-label="Suíte do rascunho"
      className="border-border rounded border px-3 py-2 text-[12px]"
    >
      <p className={green ? "text-green-600 dark:text-green-500" : "text-muted-foreground"}>
        {text}
      </p>
      {blocked && (
        <p className="text-destructive mt-0.5">
          Publicação bloqueada pelo gate: {settings.reason}. Rode a suíte na aba Testes.
        </p>
      )}
    </div>
  );
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

function compressionText(
  compression: NonNullable<ConfigPayload["run"]>["compress_tool_results"] | undefined,
): string {
  if (!compression) return "desligada";
  const parts = [`após ${compression.after_results ?? 3}`];
  if (compression.token_limit) parts.push(`${compression.token_limit} tokens`);
  if (compression.model_id) parts.push(compression.model_id);
  return parts.join(", ");
}

/** Campos que mudam do payload vigente para o do rascunho, em frases curtas para a lista de versões. */
function diffPayload(current: ConfigPayload, draft: ConfigPayload): string[] {
  const diffs: string[] = [];
  if (current.model_id !== draft.model_id)
    diffs.push(`modelo: ${current.model_id} → ${draft.model_id}`);
  const instrKeys = ["persona", "situation", "tone", "objective", "guardrails"] as const;
  for (const key of instrKeys) {
    if ((current.instructions?.[key] ?? "") !== (draft.instructions?.[key] ?? ""))
      diffs.push(`instruções.${key}`);
  }
  const capKeys = ["extended_thinking", "structured_output", "vision"] as const;
  for (const key of capKeys) {
    if ((current.capabilities?.[key] ?? false) !== (draft.capabilities?.[key] ?? false)) {
      diffs.push(`capabilities.${key}`);
    }
  }
  // controle do run e schema (ADR-0027): mudar o schema muda o contrato de quem integra
  const runA: Partial<NonNullable<ConfigPayload["run"]>> = current.run ?? {};
  const runB: Partial<NonNullable<ConfigPayload["run"]>> = draft.run ?? {};
  if ((runA.tool_call_limit ?? null) !== (runB.tool_call_limit ?? null))
    diffs.push(
      `limite de tools: ${runA.tool_call_limit ?? "sem"} → ${runB.tool_call_limit ?? "sem"}`,
    );
  if ((runA.provider_retries ?? 0) !== (runB.provider_retries ?? 0))
    diffs.push(`retry do provedor: ${runA.provider_retries ?? 0} → ${runB.provider_retries ?? 0}`);
  const fallA = (runA.fallback_models ?? []).join(", ") || "nenhum";
  const fallB = (runB.fallback_models ?? []).join(", ") || "nenhum";
  if (fallA !== fallB) diffs.push(`modelos reserva: ${fallA} → ${fallB}`);
  const compA = compressionText(runA.compress_tool_results);
  const compB = compressionText(runB.compress_tool_results);
  if (compA !== compB) diffs.push(`compressão de tool: ${compA} → ${compB}`);
  if ((runA.max_cost_usd ?? null) !== (runB.max_cost_usd ?? null))
    diffs.push(
      `teto de custo por resposta: ${runA.max_cost_usd ?? "sem"} → ${runB.max_cost_usd ?? "sem"}`,
    );
  const schemaA = current.output_schema ? JSON.stringify(current.output_schema) : null;
  const schemaB = draft.output_schema ? JSON.stringify(draft.output_schema) : null;
  if (schemaA !== schemaB)
    diffs.push(
      schemaA === null
        ? "schema de saída ligado"
        : schemaB === null
          ? "schema de saída desligado"
          : "schema de saída alterado",
    );
  return diffs;
}

export function VersionsPanel({
  agentId,
  currentVersionId,
  draftVersionId,
  hasUnsavedChanges = false,
  suite = false,
  canary = false,
}: Props) {
  const queryClient = useQueryClient();
  const [pending, setPending] = useState<Pending | null>(null);
  const { data: settings } = useEvalSettings(agentId, suite);
  const { data: cases = [] } = useEvalCases(agentId, suite);
  const blocked = suite && !!settings?.require_passing_evals && !settings.can_publish;
  const { data: canaryState } = useCanary(agentId, canary);
  const canaryOn = !!canaryState?.active;
  const canaryVersionId = canaryState?.canary?.version_id;

  const {
    data: versions,
    isPending,
    isError,
  } = useQuery<AgentConfigVersionDetail[]>({
    queryKey: ["versions", agentId],
    queryFn: async () => {
      const result = await client.GET("/api/v1/configs/{config_id}/versions", {
        params: { path: { config_id: agentId } },
      });
      if (result.error) throw new Error("Falha ao carregar versões");
      return result.data!;
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const result = await client.POST("/api/v1/configs/{config_id}/publish", {
        params: { path: { config_id: agentId } },
      });
      // o 409 do gate explica por que não publicou
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Erro ao publicar. Tente novamente."));
      return result.data!;
    },
    onError: (error) => toast.error(error.message),
    onSuccess: (version) => {
      toast.success(`v${version.version_number} publicada`);
      void queryClient.invalidateQueries({ queryKey: ["versions", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["config", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      void queryClient.invalidateQueries({ queryKey: ["eval-settings", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["canary", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: async (versionId: string) => {
      const result = await client.POST("/api/v1/configs/{config_id}/rollback", {
        params: { path: { config_id: agentId } },
        body: { version_id: versionId },
      });
      if (result.error) throw new Error("Falha ao reverter");
      return result.data!;
    },
    onError: () => toast.error("Erro ao reverter. Tente novamente."),
    onSuccess: (version) => {
      toast.success(`v${version.version_number} ativa de novo`);
      void queryClient.invalidateQueries({ queryKey: ["versions", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["config", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      void queryClient.invalidateQueries({ queryKey: ["canary", agentId] });
      void queryClient.invalidateQueries({ queryKey: ["audit"] });
    },
  });

  const draft =
    draftVersionId === undefined
      ? versions?.find((version) => version.status === "draft")
      : versions?.find((version) => version.id === draftVersionId);
  const current = versions?.find((version) => version.id === currentVersionId);
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
            disabled={busy || pending !== null || blocked}
          >
            {publishMutation.isPending ? "Publicando…" : "Publicar"}
          </Button>
        )}
      </div>

      {suite && draft && <SuiteStatus settings={settings} cases={cases.length} />}

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
          {canaryOn && (
            <p className="text-[11px] text-amber-600 dark:text-amber-400">
              O canário em andamento é desligado.
            </p>
          )}
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

      {canary && versions && (
        <CanaryPanel
          configId={agentId}
          versions={versions}
          currentVersionId={currentVersionId}
          draftVersionId={draft?.id ?? null}
          draftBlocked={blocked}
        />
      )}

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && <p className="text-destructive text-[13px]">Erro ao carregar versões.</p>}

      {!isPending && !isError && versions && versions.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhuma versão salva.</p>
      )}

      {!isPending && !isError && versions && versions.length > 0 && (
        <ul className="flex flex-col gap-1">
          {versions.map((version) => {
            const diffs =
              version.status === "draft" && current
                ? diffPayload(current.payload, version.payload)
                : [];

            return (
              <li
                key={version.id}
                className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-foreground text-[13px] font-medium">
                      v{version.version_number}
                    </span>
                    <span
                      className={`text-[11px] font-medium ${STATUS_CLS[version.status] ?? "text-muted-foreground"}`}
                    >
                      {STATUS_LABELS[version.status] ?? version.status}
                    </span>
                    <span className="text-muted-foreground text-[11px]">{version.author}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-[11px]">
                      {new Date(version.created_at).toLocaleDateString("pt-BR")}
                    </span>
                    {version.id === currentVersionId && <Badge tone="active">Ativa</Badge>}
                    {version.id === canaryVersionId && (
                      <Badge tone="pending">Canário {canaryState?.percent}%</Badge>
                    )}
                    {version.status === "published" &&
                      version.id !== currentVersionId &&
                      version.id !== canaryVersionId && (
                        <Button
                          size="xs"
                          onClick={() =>
                            setPending({
                              kind: "rollback",
                              versionId: version.id,
                              versionNumber: version.version_number,
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

      {/* a trilha é só do owner (ADR-0041) */}
      {canary && <OwnerHistory configId={agentId} />}
    </div>
  );
}
