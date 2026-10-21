"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

type Budget = components["schemas"]["BudgetResponse"];

const inputCls =
  "w-24 rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

export function formatUsd(value: number): string {
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: value > 0 && value < 0.01 ? 4 : 2,
  });
}

const LEVEL_TEXT: Record<NonNullable<Budget["level"]>, string> = {
  ok: "dentro do orçamento",
  warning: "perto do limite",
  exceeded: "orçamento estourado",
};

const BAR_CLS: Record<NonNullable<Budget["level"]>, string> = {
  ok: "bg-accent",
  warning: "bg-amber-500",
  exceeded: "bg-destructive",
};

export function BudgetSection({ configId }: { configId: string }) {
  const { data, isError } = useQuery<Budget>({
    queryKey: ["budget", configId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/budget", {
        params: { path: { config_id: configId } },
      });
      if (res.error) throw new Error("Falha ao carregar o orçamento");
      return res.data!;
    },
  });
  if (isError) {
    return <p className="text-destructive text-[12px]">Falha ao carregar o orçamento.</p>;
  }
  if (!data) return null;
  // o formulário remonta com o que a API salvou
  return (
    <BudgetCard
      key={`${data.monthly_usd}-${data.alert_percent}-${data.hard_stop}`}
      configId={configId}
      data={data}
    />
  );
}

function BudgetCard({ configId, data }: { configId: string; data: Budget }) {
  const queryClient = useQueryClient();
  const [limit, setLimit] = useState(data.monthly_usd != null ? String(data.monthly_usd) : "");
  const [alertPercent, setAlertPercent] = useState(data.alert_percent);
  const [hardStop, setHardStop] = useState(data.hard_stop);

  const save = useMutation({
    mutationFn: async () => {
      const value = limit.trim() ? Number(limit.replace(",", ".")) : null;
      const res = await client.PUT("/api/v1/configs/{config_id}/budget", {
        params: { path: { config_id: configId } },
        body: { monthly_usd: value, alert_percent: alertPercent, hard_stop: hardStop },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o orçamento"));
      return res.data!;
    },
    onSuccess: (saved) => queryClient.setQueryData(["budget", configId], saved),
  });

  const width = Math.min(data.percent ?? 0, 100);

  return (
    <section
      aria-label="Orçamento do mês"
      className="border-border bg-card flex flex-col gap-2 rounded border px-3 py-2.5"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-foreground text-[13px] font-medium">Orçamento do mês</span>
        <span className="text-muted-foreground text-[12px]" role="status">
          {formatUsd(data.spent_usd)} gastos
          {data.monthly_usd != null && ` de ${formatUsd(data.monthly_usd)}`}
          {data.level && ` · ${LEVEL_TEXT[data.level]}`}
        </span>
      </div>
      {data.level && (
        <div
          className="bg-muted h-1.5 overflow-hidden rounded"
          role="meter"
          aria-label="Gasto sobre o orçamento"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(width)}
        >
          <div className={`h-full ${BAR_CLS[data.level]}`} style={{ width: `${width}%` }} />
        </div>
      )}
      <p className="text-muted-foreground text-[11px]">
        Custo estimado pela tabela de preços do modelo, somando conversas, testes e busca com HyDE.
        Mudar o limite não pede nova versão.
      </p>
      <form
        className="text-muted-foreground flex flex-wrap items-center gap-3 text-[12px]"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <label className="flex items-center gap-1">
          Limite em US$
          <input
            inputMode="decimal"
            value={limit}
            onChange={(e) => setLimit(e.target.value)}
            placeholder="sem limite"
            className={inputCls}
          />
        </label>
        <label className="flex items-center gap-1">
          Avisar em
          <input
            type="number"
            min={1}
            max={99}
            value={alertPercent}
            onChange={(e) => setAlertPercent(Number(e.target.value))}
            className={`${inputCls} w-16`}
          />
          %
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={hardStop}
            onChange={(e) => setHardStop(e.target.checked)}
          />
          Barrar runs ao estourar
        </label>
        <Button size="xs" variant="strong" type="submit" disabled={save.isPending}>
          {save.isPending ? "Salvando…" : "Salvar orçamento"}
        </Button>
      </form>
      {hardStop && (
        <p className="text-muted-foreground text-[11px]">
          Estourado, o agente responde com a mensagem de orçamento esgotado até o mês virar ou o
          limite subir. Os avisos saem pelos destinos da página Alertas.
        </p>
      )}
      {save.error && (
        <p className="text-destructive text-[12px]" role="alert">
          {save.error.message}
        </p>
      )}
    </section>
  );
}
