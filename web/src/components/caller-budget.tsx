"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

type CallerBudget = components["schemas"]["CallerBudgetResponse"];

const KEY = ["caller-budgets"];
const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground focus:border-accent focus:outline-none";

function usd(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

/** Orçamentos de quem chama (ADR-0031): uma consulta para a página inteira. */
export function useCallerBudgets() {
  return useQuery({
    queryKey: KEY,
    queryFn: async (): Promise<Record<string, CallerBudget>> => {
      const res = await client.GET("/api/v1/caller-budgets");
      if (res.error) throw new Error("Falha ao carregar os orçamentos");
      return Object.fromEntries(res.data.map((b) => [b.subject, b]));
    },
  });
}

/** Gasto do mês e orçamento de um usuário do painel ou token de integração. */
export function CallerBudgetEditor({ subject, label }: { subject: string; label: string }) {
  const queryClient = useQueryClient();
  const { data } = useCallerBudgets();
  const current = data?.[subject];
  const [editing, setEditing] = useState(false);
  const [limit, setLimit] = useState("");
  const [warn, setWarn] = useState(80);
  const [hardStop, setHardStop] = useState(false);

  function open() {
    setLimit(current ? String(current.monthly_usd) : "");
    setWarn(current?.warn_percent ?? 80);
    setHardStop(current?.hard_stop ?? false);
    setEditing(true);
  }

  const save = useMutation({
    mutationFn: async () => {
      const res = await client.PUT("/api/v1/caller-budgets/{subject}", {
        params: { path: { subject } },
        body: { monthly_usd: Number(limit), warn_percent: warn, hard_stop: hardStop },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o orçamento"));
    },
    onSuccess: () => {
      toast.success(`Orçamento de ${label} salvo`);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/caller-budgets/{subject}", {
        params: { path: { subject } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover o orçamento"));
    },
    onSuccess: () => {
      toast.success(`Orçamento de ${label} removido`);
      setEditing(false);
      void queryClient.invalidateQueries({ queryKey: KEY });
    },
    onError: (e) => toast.error(e.message),
  });

  if (editing) {
    const invalid = !(Number(limit) > 0);
    return (
      <div role="group" aria-label={`Orçamento de ${label}`} className="flex flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2 text-[13px]">
          <label className="text-foreground flex items-center gap-1.5">
            US$
            <input
              type="number"
              aria-label="Limite do mês em dólar"
              min={0.01}
              step={0.01}
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              className={`${inputCls} w-24`}
            />
            por mês
          </label>
          <label className="text-foreground flex items-center gap-1.5">
            aviso em
            <input
              type="number"
              aria-label="Aviso em porcentagem do limite"
              min={1}
              max={100}
              value={warn}
              onChange={(e) => setWarn(Number(e.target.value))}
              className={`${inputCls} w-16`}
            />
            %
          </label>
          <label className="text-foreground flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={hardStop}
              onChange={(e) => setHardStop(e.target.checked)}
            />
            Bloquear ao estourar
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            size="xs"
            variant="strong"
            disabled={invalid || save.isPending}
            onClick={() => save.mutate()}
          >
            Salvar orçamento
          </Button>
          {current && (
            <Button
              size="xs"
              variant="subtleDestructive"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Remover orçamento
            </Button>
          )}
          <Button size="xs" variant="muted" onClick={() => setEditing(false)}>
            Cancelar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-[12px]">
      {current ? (
        <span
          className={
            current.level === "exceeded"
              ? "text-destructive"
              : current.level === "warning"
                ? "text-amber-600 dark:text-amber-400"
                : "text-muted-foreground"
          }
        >
          {usd(current.spent_usd)} de {usd(current.monthly_usd)} no mês (
          {current.percent.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%)
          {current.hard_stop ? " · bloqueia ao estourar" : ""}
        </span>
      ) : (
        <span className="text-muted-foreground">Sem orçamento</span>
      )}
      <Button size="xs" variant="muted" onClick={open} aria-label={`Orçamento de ${label}`}>
        {current ? "Editar" : "Definir orçamento"}
      </Button>
    </div>
  );
}
