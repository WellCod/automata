"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type MemoryItem = components["schemas"]["MemoryItem"];

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function when(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "";
}

export function groupByUser(items: MemoryItem[]): [string, MemoryItem[]][] {
  const groups = new Map<string, MemoryItem[]>();
  for (const m of items) {
    const key = m.user_id ?? "?";
    groups.set(key, [...(groups.get(key) ?? []), m]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

/** Memórias de um agente, por usuário (ADR-0025). Só o owner vê: a API devolve 403 ao resto. */
export function MemoriesPanel({ agentId }: { agentId: string }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState("");
  const key = ["memories", agentId, user];
  const { data, isPending, isError } = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/memories", {
        params: { path: { config_id: agentId }, query: user ? { user_id: user } : {} },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao carregar memórias"));
      return res.data!;
    },
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["memories", agentId] });
  const removeOne = useMutation({
    mutationFn: async (memoryId: string) => {
      const res = await client.DELETE("/api/v1/configs/{config_id}/memories/{memory_id}", {
        params: { path: { config_id: agentId, memory_id: memoryId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao apagar"));
    },
    onSuccess: refresh,
    onError: (e) => toast.error(e.message),
  });
  const forget = useMutation({
    mutationFn: async (userId: string) => {
      const res = await client.DELETE("/api/v1/configs/{config_id}/memories", {
        params: { path: { config_id: agentId }, query: { user_id: userId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao apagar"));
    },
    onSuccess: (_, userId) => {
      toast.success(`Memórias de ${userId} apagadas`);
      refresh();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-[13px]">
        O que este agente lembra de cada usuário. Para atender um pedido de exclusão, apague tudo de
        um usuário. As memórias também somem sozinhas depois do prazo de retenção.
      </p>
      <input
        aria-label="Filtrar por usuário"
        value={user}
        onChange={(e) => setUser(e.target.value.trim())}
        placeholder="ID do usuário"
        className={`${inputCls} max-w-xs`}
      />
      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar as memórias. Só o owner da instância vê memórias de usuários.
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhuma memória guardada.</p>
      )}
      {data &&
        groupByUser(data).map(([userId, items]) => (
          <section
            key={userId}
            aria-label={`Memórias de ${userId}`}
            className="border-border bg-card flex flex-col gap-1.5 rounded border px-3 py-2"
          >
            <div className="flex items-center justify-between gap-2">
              <code className="text-foreground text-[12px]">{userId}</code>
              <Button
                size="xs"
                variant="subtleDestructive"
                disabled={forget.isPending}
                onClick={() => {
                  if (window.confirm(`Apagar tudo o que este agente lembra de ${userId}?`))
                    forget.mutate(userId);
                }}
              >
                Esquecer usuário
              </Button>
            </div>
            <ul className="flex flex-col gap-1">
              {items.map((m) => (
                <li
                  key={m.memory_id}
                  className="flex items-start justify-between gap-2 text-[13px]"
                >
                  <span className="text-foreground">
                    {m.memory}
                    <span className="text-muted-foreground text-[11px]">
                      {" "}
                      · {when(m.updated_at)}
                    </span>
                  </span>
                  <Button
                    size="xs"
                    variant="ghost"
                    aria-label={`Apagar memória: ${m.memory}`}
                    onClick={() => removeOne.mutate(m.memory_id)}
                  >
                    Apagar
                  </Button>
                </li>
              ))}
            </ul>
          </section>
        ))}
    </div>
  );
}
