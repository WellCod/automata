"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";
import { formatDuration, formatTotalUsd } from "@/lib/format";

type CanaryState = components["schemas"]["CanaryState"];
type VersionStats = components["schemas"]["VersionStats"];
type Version = components["schemas"]["AgentConfigVersionDetail"];

const MAX_PERCENT = 50;
const DRAFT = "draft";

const inputCls =
  "w-16 rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";
const selectCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

const pctFmt = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });

interface Props {
  configId: string;
  versions: Version[];
  currentVersionId?: string | null;
  // o gate da suíte barra o canário a partir do rascunho, como a publicação
  draftBlocked?: boolean;
}

export function useCanary(configId: string, enabled = true) {
  return useQuery<CanaryState>({
    queryKey: ["canary", configId],
    enabled,
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/canary", {
        params: { path: { config_id: configId } },
      });
      if (res.error) throw new Error("Falha ao carregar o canário");
      return res.data!;
    },
  });
}

function suiteText(stats: VersionStats): string {
  const s = stats.suite;
  if (!s) return "—";
  if (s.status === "failed") return "falhou";
  if (s.status !== "completed") return "rodando";
  return `${s.passed} de ${s.total}`;
}

const ROWS: { label: string; value: (s: VersionStats) => string }[] = [
  { label: "Conversas", value: (s) => s.runs.toLocaleString("pt-BR") },
  { label: "Taxa de erro", value: (s) => (s.runs ? pctFmt.format(s.error_rate) : "—") },
  { label: "p50", value: (s) => formatDuration(s.p50_ms) },
  { label: "p95", value: (s) => formatDuration(s.p95_ms) },
  { label: "Custo médio", value: (s) => formatTotalUsd(s.avg_cost) },
  { label: "Última suíte", value: suiteText },
];

function Comparison({ current, canary }: { current: VersionStats; canary: VersionStats }) {
  return (
    <table className="w-full text-[12px]" aria-label="Comparação entre a vigente e o canário">
      <thead>
        <tr className="text-muted-foreground text-left">
          <th className="py-1 font-normal" />
          <th className="py-1 font-medium">v{current.version_number} (vigente)</th>
          <th className="py-1 font-medium">v{canary.version_number} (canário)</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.map((row) => (
          <tr key={row.label} className="border-border border-t">
            <th scope="row" className="text-muted-foreground py-1 text-left font-normal">
              {row.label}
            </th>
            <td className="text-foreground py-1 tabular-nums">{row.value(current)}</td>
            <td className="text-foreground py-1 tabular-nums">{row.value(canary)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function CanaryPanel({ configId, versions, currentVersionId, draftBlocked = false }: Props) {
  const queryClient = useQueryClient();
  const { data: state, isError } = useCanary(configId);
  const draft = versions.find((v) => v.status === "draft");
  const others = versions.filter((v) => v.status === "published" && v.id !== currentVersionId);
  const [source, setSource] = useState<string>("");
  const [percent, setPercent] = useState(10);
  const [newPercent, setNewPercent] = useState<number | null>(null);
  const [confirming, setConfirming] = useState<"promote" | "stop" | null>(null);

  const chosen = source || (draft ? DRAFT : (others[0]?.id ?? ""));

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["canary", configId] });
    void queryClient.invalidateQueries({ queryKey: ["versions", configId] });
    void queryClient.invalidateQueries({ queryKey: ["config", configId] });
    void queryClient.invalidateQueries({ queryKey: ["configs"] });
    void queryClient.invalidateQueries({ queryKey: ["eval-settings", configId] });
  }

  const start = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/configs/{config_id}/canary", {
        params: { path: { config_id: configId } },
        body: { percent, version_id: chosen === DRAFT ? null : chosen },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Erro ao ligar o canário."));
      return res.data!;
    },
    onError: (e) => toast.error(e.message),
    onSuccess: (s) => {
      toast.success(`v${s.canary?.version_number} em ${s.percent}% das conversas`);
      setSource("");
      refresh();
    },
  });

  const change = useMutation({
    mutationFn: async (value: number) => {
      const res = await client.PATCH("/api/v1/configs/{config_id}/canary", {
        params: { path: { config_id: configId } },
        body: { percent: value },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Erro ao mudar o percentual."));
      return res.data!;
    },
    onError: (e) => toast.error(e.message),
    onSuccess: (s) => {
      toast.success(`Canário em ${s.percent}% das conversas`);
      setNewPercent(null);
      refresh();
    },
  });

  const finish = useMutation({
    mutationFn: async (kind: "promote" | "stop") => {
      const res =
        kind === "promote"
          ? await client.POST("/api/v1/configs/{config_id}/canary/promote", {
              params: { path: { config_id: configId } },
            })
          : await client.DELETE("/api/v1/configs/{config_id}/canary", {
              params: { path: { config_id: configId } },
            });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Erro ao encerrar o canário."));
      return kind;
    },
    onError: (e) => toast.error(e.message),
    onSuccess: (kind) => {
      toast.success(kind === "promote" ? "Canário promovido a vigente" : "Canário desligado");
      setConfirming(null);
      refresh();
    },
  });

  if (isError) return <p className="text-destructive text-[12px]">Erro ao carregar o canário.</p>;
  if (!state || !currentVersionId) return null;

  if (state.active && state.canary) {
    const canary = state.canary;
    const busy = change.isPending || finish.isPending;
    return (
      <section
        aria-label="Canário"
        className="border-border bg-card flex flex-col gap-3 rounded border px-3 py-3"
      >
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="text-foreground text-[13px] font-medium">
            Canário: v{canary.version_number} em {state.percent}% das conversas
          </h3>
          {state.started_at && (
            <span className="text-muted-foreground text-[11px]">
              desde {new Date(state.started_at).toLocaleString("pt-BR")}
            </span>
          )}
        </div>
        <p className="text-muted-foreground text-[12px]">
          Cada conversa fica sempre na mesma versão. O modo teste continua usando a versão que você
          escolher.
        </p>
        {state.current && <Comparison current={state.current} canary={canary} />}

        <form
          className="flex flex-wrap items-center gap-2 text-[12px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (newPercent !== null) change.mutate(newPercent);
          }}
        >
          <label className="text-muted-foreground flex items-center gap-1">
            Percentual
            <input
              type="number"
              min={1}
              max={MAX_PERCENT}
              value={newPercent ?? state.percent ?? 10}
              onChange={(e) => setNewPercent(Number(e.target.value))}
              className={inputCls}
            />
            %
          </label>
          <Button size="xs" type="submit" disabled={busy || newPercent === null}>
            Ajustar
          </Button>
          <div className="ml-auto flex gap-2">
            <Button size="xs" onClick={() => setConfirming("stop")} disabled={busy}>
              Desligar
            </Button>
            <Button
              size="xs"
              variant="accent"
              onClick={() => setConfirming("promote")}
              disabled={busy}
            >
              Promover v{canary.version_number}
            </Button>
          </div>
        </form>

        {confirming && (
          <div role="alertdialog" aria-label="Confirmar" className="flex flex-col gap-2">
            <p className="text-foreground text-[13px]">
              {confirming === "promote"
                ? `Promover v${canary.version_number}? Ela passa a responder em todas as conversas.`
                : "Desligar o canário? Todas as conversas voltam para a vigente."}
            </p>
            <div className="flex justify-end gap-2">
              <Button size="sm" onClick={() => setConfirming(null)}>
                Cancelar
              </Button>
              <Button variant="accent" size="sm" onClick={() => finish.mutate(confirming)}>
                {confirming === "promote" ? "Confirmar promoção" : "Confirmar"}
              </Button>
            </div>
          </div>
        )}
      </section>
    );
  }

  if (!draft && others.length === 0) return null;
  const blocked = chosen === DRAFT && draftBlocked;

  return (
    <section
      aria-label="Canário"
      className="border-border flex flex-col gap-2 rounded border px-3 py-3"
    >
      <h3 className="text-foreground text-[13px] font-medium">Liberação gradual</h3>
      <p className="text-muted-foreground text-[12px]">
        Uma parte das conversas passa a usar outra versão, sem mexer na vigente. Compare os números
        e promova quando estiver seguro.
      </p>
      <form
        className="flex flex-wrap items-center gap-2 text-[12px]"
        onSubmit={(e) => {
          e.preventDefault();
          start.mutate();
        }}
      >
        <label className="text-muted-foreground flex items-center gap-1">
          Versão
          <select value={chosen} onChange={(e) => setSource(e.target.value)} className={selectCls}>
            {draft && <option value={DRAFT}>Rascunho (vira v{draft.version_number + 1})</option>}
            {others.map((v) => (
              <option key={v.id} value={v.id}>
                v{v.version_number}
              </option>
            ))}
          </select>
        </label>
        <label className="text-muted-foreground flex items-center gap-1">
          em
          <input
            type="number"
            min={1}
            max={MAX_PERCENT}
            value={percent}
            onChange={(e) => setPercent(Number(e.target.value))}
            className={inputCls}
          />
          % das conversas
        </label>
        <Button size="xs" variant="strong" type="submit" disabled={start.isPending || blocked}>
          {start.isPending ? "Ligando…" : "Ligar canário"}
        </Button>
      </form>
      {blocked && (
        <p className="text-destructive text-[11px]">
          O rascunho precisa da suíte verde para virar canário, como na publicação.
        </p>
      )}
    </section>
  );
}
