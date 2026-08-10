"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { AgentCard } from "@/components/agent-card";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

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
    <form
      onSubmit={handleSubmit}
      className="border-border bg-card flex items-center gap-2 rounded border px-3 py-2"
    >
      <input
        ref={inputRef}
        autoFocus
        placeholder="Nome do agente"
        className="text-foreground placeholder:text-muted-foreground min-w-0 flex-1 bg-transparent text-[13px] focus:outline-none"
        disabled={mutation.isPending}
      />
      <button
        type="submit"
        disabled={mutation.isPending}
        className="border-accent text-accent hover:border-accent/70 hover:text-accent/70 inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
      >
        {mutation.isPending ? "Criando…" : "Criar"}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="text-muted-foreground hover:text-foreground text-[10px] tracking-[0.05em] uppercase transition-colors"
      >
        Cancelar
      </button>
      {mutation.isError && <span className="text-destructive text-[10px]">Erro ao criar</span>}
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
    <div className="w-full px-6 py-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-foreground text-sm font-medium">Agentes</h1>
          {data && (
            <p className="text-muted-foreground mt-0.5 text-[13px]">
              {data.total} agente{data.total !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <button
          onClick={() => setShowNew(true)}
          className="border-accent text-accent hover:border-accent/70 hover:text-accent/70 inline-flex h-7 items-center gap-1.5 rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors"
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
            className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent w-full rounded border bg-[var(--input)] py-1.5 pr-3 pl-9 text-[13px] focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as StatusFilter);
            setPage(1);
          }}
          className="border-border text-foreground focus:border-accent rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] focus:outline-none"
        >
          <option value="">Todos</option>
          <option value="published">Com versão ativa</option>
          <option value="draft">Com rascunho</option>
        </select>
      </div>

      {isPending ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          <span className="sr-only">Carregando…</span>
          {[...Array(6)].map((_, i) => (
            <div key={i} className="border-border bg-card h-28 animate-pulse rounded border" />
          ))}
        </div>
      ) : isError ? (
        <div className="border-destructive/30 bg-destructive/10 text-destructive rounded border py-8 text-center text-[13px]">
          Erro ao carregar agentes.
        </div>
      ) : data.items.length === 0 ? (
        <div className="border-border rounded border py-16 text-center">
          <p className="text-foreground text-[13px] font-medium">Nenhum agente encontrado</p>
          <p className="text-muted-foreground mt-1 text-[13px]">
            {q || status ? "Tente outros filtros" : 'Clique em "Novo agente" para começar'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="text-muted-foreground mt-4 flex items-center justify-end gap-2 text-[13px]">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="hover:border-border hover:text-foreground rounded border border-transparent p-1 transition-colors disabled:opacity-40"
            aria-label="Página anterior"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="hover:border-border hover:text-foreground rounded border border-transparent p-1 transition-colors disabled:opacity-40"
            aria-label="Próxima página"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
