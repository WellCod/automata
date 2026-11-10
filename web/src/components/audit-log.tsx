"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { ACTION_FILTERS, auditLabel, describeDetail } from "@/lib/audit-labels";

type AuditPage = components["schemas"]["AuditPage"];

const selectCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[12px] text-foreground focus:border-accent focus:outline-none";

const PERIODS = [
  { value: "7", label: "Últimos 7 dias" },
  { value: "30", label: "Últimos 30 dias" },
  { value: "90", label: "Últimos 90 dias" },
  { value: "", label: "Tudo" },
];

const KIND_PATH: Record<string, string> = {
  agent: "/agents",
  team: "/times",
  workflow: "/workflows",
};

function since(days: string): string | undefined {
  if (!days) return undefined;
  return new Date(Date.now() - Number(days) * 86_400_000).toISOString();
}

interface Props {
  // na aba Versões: só as ações daquele agente ou time, sem filtros
  configId?: string;
}

export function AuditLog({ configId }: Props) {
  const [action, setAction] = useState("");
  const [period, setPeriod] = useState("30");
  const [actor, setActor] = useState<{ id: string; label: string } | null>(null);
  const compact = !!configId;

  const query = useInfiniteQuery({
    queryKey: ["audit", configId ?? null, action, period, actor?.id ?? null],
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam }): Promise<AuditPage> => {
      const res = await client.GET("/api/v1/audit", {
        params: {
          query: {
            config_id: configId,
            action: action || undefined,
            since: compact ? undefined : since(period),
            actor: actor?.id,
            cursor: pageParam ?? undefined,
            limit: compact ? 10 : 50,
          },
        },
      });
      if (res.error) throw new Error("Falha ao carregar a trilha. Apenas owners têm acesso.");
      return res.data!;
    },
    getNextPageParam: (last) => last.next_cursor ?? null,
  });

  const pages = query.data?.pages ?? [];
  const items = pages.flatMap((p) => p.items);
  const configs = Object.assign({}, ...pages.map((p) => p.configs)) as AuditPage["configs"];
  const versions = Object.assign({}, ...pages.map((p) => p.versions)) as AuditPage["versions"];

  return (
    <div className="flex flex-col gap-3">
      {!compact && (
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <label className="text-muted-foreground flex items-center gap-1">
            Ação
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className={selectCls}
            >
              <option value="">Todas</option>
              {ACTION_FILTERS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-muted-foreground flex items-center gap-1">
            Período
            <select
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              className={selectCls}
            >
              {PERIODS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
          {actor && (
            <Button size="xs" variant="muted" onClick={() => setActor(null)}>
              Só {actor.label} ✕
            </Button>
          )}
        </div>
      )}

      {query.isLoading && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {query.error && <p className="text-destructive text-[13px]">{query.error.message}</p>}
      {!query.isLoading && !query.error && items.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhuma ação registrada.</p>
      )}

      {items.length > 0 && (
        <ul className="flex flex-col" aria-label="Trilha de auditoria">
          {items.map((e) => {
            const config = e.config_id ? configs[e.config_id] : undefined;
            const who = e.actor_label ?? e.actor ?? "sem autenticação";
            const changes = describeDetail(e.detail, versions);
            const failed = e.status_code >= 400;
            return (
              <li
                key={e.id}
                className="border-border flex flex-col gap-0.5 border-t py-2 text-[13px]"
              >
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-foreground font-medium">{auditLabel(e.action)}</span>
                  {!compact && config && e.config_id && (
                    <Link
                      href={`${KIND_PATH[config.kind] ?? "/agents"}/${e.config_id}`}
                      className="text-accent hover:underline"
                    >
                      {config.name}
                    </Link>
                  )}
                  {failed && (
                    <span className="text-destructive text-[11px]">recusada ({e.status_code})</span>
                  )}
                </div>
                {changes.length > 0 && (
                  <p className="text-muted-foreground text-[12px]">{changes.join(" · ")}</p>
                )}
                <p className="text-muted-foreground text-[11px]">
                  {new Date(e.created_at).toLocaleString("pt-BR")} ·{" "}
                  {compact || !e.actor ? (
                    who
                  ) : (
                    <button
                      type="button"
                      className="hover:text-foreground min-h-6 underline-offset-2 hover:underline"
                      onClick={() => setActor({ id: e.actor!, label: who })}
                    >
                      {who}
                    </button>
                  )}
                  {!compact && e.ip ? ` · ${e.ip}` : ""}
                </p>
              </li>
            );
          })}
        </ul>
      )}

      {query.hasNextPage && (
        <Button
          size="sm"
          variant="muted"
          className="self-start"
          disabled={query.isFetchingNextPage}
          onClick={() => void query.fetchNextPage()}
        >
          {query.isFetchingNextPage ? "Carregando…" : "Mais antigas"}
        </Button>
      )}
    </div>
  );
}
