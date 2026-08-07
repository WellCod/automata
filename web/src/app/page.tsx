"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useState } from "react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfig = components["schemas"]["AgentConfigResponse"];
type StatusFilter = components["schemas"]["ConfigPayloadStatus"] | "";

const PAGE_SIZE = 20;

async function fetchConfigs(page: number, q: string, status: StatusFilter) {
  const res = await client.GET("/api/v1/configs", {
    params: {
      query: {
        page,
        page_size: PAGE_SIZE,
        q: q || undefined,
        status: status || undefined,
      },
    },
  });
  if (res.error) throw new Error("Falha ao carregar agentes");
  return res.data!;
}

function VersionBadge({ label, variant }: { label: string; variant: "green" | "amber" | "zinc" }) {
  const colors = {
    green: "bg-green-100 text-green-800",
    amber: "bg-amber-100 text-amber-800",
    zinc: "bg-zinc-100 text-zinc-500",
  };
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${colors[variant]}`}
    >
      {label}
    </span>
  );
}

function AgentRow({ agent }: { agent: AgentConfig }) {
  const { current_version, draft_version } = agent;
  return (
    <tr className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50">
      <td className="py-3 pr-4">
        <p className="text-sm font-medium text-zinc-900">{agent.name}</p>
        {agent.description && (
          <p className="mt-0.5 max-w-xs truncate text-xs text-zinc-400">{agent.description}</p>
        )}
      </td>
      <td className="py-3 pr-4">
        <div className="flex flex-wrap gap-1">
          {current_version ? (
            <VersionBadge label={`v${current_version.version_number}`} variant="green" />
          ) : (
            <VersionBadge label="sem versão" variant="zinc" />
          )}
          {draft_version && <VersionBadge label="rascunho" variant="amber" />}
        </div>
      </td>
      <td className="hidden py-3 pr-4 text-xs text-zinc-400 sm:table-cell">
        {new Date(agent.updated_at).toLocaleDateString("pt-BR")}
      </td>
    </tr>
  );
}

export default function AgentsPage() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<StatusFilter>("");

  const { data, isPending, isError } = useQuery({
    queryKey: ["configs", page, q, status],
    queryFn: () => fetchConfigs(page, q, status),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="mb-6 text-2xl font-semibold text-zinc-900">Agentes</h1>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-zinc-400"
            aria-hidden
          />
          <input
            type="text"
            placeholder="Buscar por nome ou ID…"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(1);
            }}
            className="w-full rounded-md border border-zinc-200 py-2 pr-3 pl-9 text-sm text-zinc-900 placeholder:text-zinc-400 focus:border-zinc-400 focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as StatusFilter);
            setPage(1);
          }}
          className="rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-700 focus:border-zinc-400 focus:outline-none"
        >
          <option value="">Todos</option>
          <option value="published">Com versão ativa</option>
          <option value="draft">Com rascunho</option>
        </select>
      </div>

      <div className="rounded-lg border border-zinc-200 bg-white">
        {isPending ? (
          <div className="py-12 text-center text-sm text-zinc-400">Carregando…</div>
        ) : isError ? (
          <div className="py-12 text-center text-sm text-red-500">Erro ao carregar agentes.</div>
        ) : data.items.length === 0 ? (
          <div className="py-12 text-center text-sm text-zinc-400">Nenhum agente encontrado.</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-zinc-100">
                <th className="pt-3 pr-4 pb-2 text-left text-xs font-medium text-zinc-500">Nome</th>
                <th className="pt-3 pr-4 pb-2 text-left text-xs font-medium text-zinc-500">
                  Versão
                </th>
                <th className="hidden pt-3 pr-4 pb-2 text-left text-xs font-medium text-zinc-500 sm:table-cell">
                  Atualizado
                </th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((agent) => (
                <AgentRow key={agent.id} agent={agent} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm text-zinc-500">
          <span>
            {data?.total} agente{data?.total !== 1 ? "s" : ""}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded p-1 hover:bg-zinc-100 disabled:opacity-40"
              aria-label="Página anterior"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span>
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded p-1 hover:bg-zinc-100 disabled:opacity-40"
              aria-label="Próxima página"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
