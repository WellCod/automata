"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
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

function StatusBadge({ agent }: { agent: AgentConfig }) {
  if (agent.current_version && agent.draft_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:ring-amber-800">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        rascunho pendente
      </span>
    );
  }
  if (agent.current_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200 dark:bg-green-950/40 dark:text-green-400 dark:ring-green-800">
        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />v
        {agent.current_version.version_number} ativo
      </span>
    );
  }
  if (agent.draft_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-500 ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700">
        <span className="h-1.5 w-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500" />
        rascunho
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-zinc-50 px-2 py-0.5 text-xs font-medium text-zinc-400 ring-1 ring-zinc-200 dark:bg-zinc-900 dark:text-zinc-600 dark:ring-zinc-800">
      sem versão
    </span>
  );
}

function AgentCard({ agent }: { agent: AgentConfig }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="group flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition-all duration-150 hover:border-zinc-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700 dark:hover:shadow-zinc-900/50"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-zinc-900 transition-colors group-hover:text-zinc-600 dark:text-zinc-100 dark:group-hover:text-zinc-300">
            {agent.name}
          </p>
          {agent.description && (
            <p className="mt-0.5 line-clamp-2 text-xs text-zinc-400 dark:text-zinc-500">
              {agent.description}
            </p>
          )}
        </div>
        <StatusBadge agent={agent} />
      </div>
      <p className="text-xs text-zinc-400 dark:text-zinc-600">
        atualizado {new Date(agent.updated_at).toLocaleDateString("pt-BR")}
      </p>
    </Link>
  );
}

function NewAgentInline({ onCancel }: { onCancel: () => void }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);

  const mutation = useMutation({
    mutationFn: async (name: string) => {
      const res = await client.POST("/api/v1/configs", { body: { name } });
      if (res.error) throw new Error("Falha ao criar agente");
      return res.data!;
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      router.push(`/agents/${data.id}`);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const name = inputRef.current?.value.trim();
    if (name) mutation.mutate(name);
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <input
        ref={inputRef}
        autoFocus
        placeholder="Nome do agente"
        className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent min-w-0 flex-1 rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] transition-colors focus:outline-none"
        disabled={mutation.isPending}
      />
      <button
        type="submit"
        disabled={mutation.isPending}
        className="border-foreground text-foreground hover:border-accent hover:text-accent rounded border px-3 py-1.5 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
      >
        {mutation.isPending ? "Criando…" : "Criar"}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-muted-foreground hover:text-foreground text-[11px] tracking-[0.05em] uppercase transition-colors"
      >
        Cancelar
      </button>
      {mutation.isError && <span className="text-destructive text-[11px]">Erro ao criar</span>}
    </form>
  );
}

export default function AgentsPage() {
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<StatusFilter>("");
  const [showNew, setShowNew] = useState(false);

  const { data, isPending, isError } = useQuery({
    queryKey: ["configs", page, q, status],
    queryFn: () => fetchConfigs(page, q, status),
  });

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">Agentes</h1>
          {data && (
            <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
              {data.total} agente{data.total !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className="border-accent text-accent hover:border-accent/70 hover:text-accent/70 inline-flex items-center gap-1.5 rounded border px-3 py-1.5 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors"
        >
          <Plus className="h-3.5 w-3.5" />
          Novo agente
        </button>
      </div>

      {showNew && (
        <div className="mb-4">
          <NewAgentInline onCancel={() => setShowNew(false)} />
        </div>
      )}

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search
            className="text-muted-foreground absolute top-1/2 left-3 h-3.5 w-3.5 -translate-y-1/2"
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
            className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent w-full rounded border bg-[var(--input)] py-1.5 pr-3 pl-9 text-[13px] transition-colors focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as StatusFilter);
            setPage(1);
          }}
          className="border-border text-foreground focus:border-accent rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] transition-colors focus:outline-none"
        >
          <option value="">Todos</option>
          <option value="published">Com versão ativa</option>
          <option value="draft">Com rascunho</option>
        </select>
      </div>

      {isPending ? (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <span className="sr-only">Carregando…</span>
          {[...Array(4)].map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-xl bg-zinc-100 dark:bg-zinc-800/50"
            />
          ))}
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-red-100 bg-red-50 py-8 text-center text-sm text-red-500 dark:border-red-900/30 dark:bg-red-950/20 dark:text-red-400">
          Erro ao carregar agentes.
        </div>
      ) : data.items.length === 0 ? (
        <div className="flex flex-col items-center gap-4 rounded-xl border border-zinc-200 bg-white py-16 dark:border-zinc-800 dark:bg-zinc-900">
          <Bot className="h-10 w-10 text-zinc-300 dark:text-zinc-700" />
          <div className="text-center">
            <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              Nenhum agente encontrado
            </p>
            <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-600">
              {q || status ? "Tente outros filtros" : 'Clique em "Novo agente" para começar'}
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {data.items.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-end gap-2 text-sm text-zinc-500 dark:text-zinc-400">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg p-1 transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:hover:bg-zinc-800"
            aria-label="Página anterior"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg p-1 transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:hover:bg-zinc-800"
            aria-label="Próxima página"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
