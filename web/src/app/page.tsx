"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Plus, Search } from "lucide-react";
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

function StatusDot({ agent }: { agent: AgentConfig }) {
  if (agent.current_version && agent.draft_version) {
    return (
      <span className="text-[11px] tracking-[0.05em] text-amber-400 uppercase">
        v{agent.current_version.version_number} · rascunho pendente
      </span>
    );
  }
  if (agent.current_version) {
    return (
      <span className="text-accent text-[11px] tracking-[0.05em] uppercase">
        v{agent.current_version.version_number} · ativo
      </span>
    );
  }
  if (agent.draft_version) {
    return (
      <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
        rascunho
      </span>
    );
  }
  return (
    <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
      sem versão
    </span>
  );
}

function AgentCard({ agent }: { agent: AgentConfig }) {
  return (
    <Link
      href={`/agents/${agent.id}`}
      className="border-border bg-card hover:border-foreground/20 flex flex-col gap-2 rounded border p-3 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-foreground truncate text-[13px] font-medium">{agent.name}</p>
        <StatusDot agent={agent} />
      </div>
      {agent.description && (
        <p className="text-muted-foreground line-clamp-1 text-[13px]">{agent.description}</p>
      )}
      <p className="border-border text-muted-foreground border-t pt-2 text-[11px] tracking-[0.05em] uppercase">
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
    <div className="flex flex-col">
      {/* Header */}
      <div className="border-border bg-background sticky top-0 z-10 flex h-11 items-center justify-between border-b px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-foreground text-sm font-medium">Agentes</h1>
          {data && (
            <span className="text-muted-foreground text-[13px]">
              {data.total} {data.total !== 1 ? "agentes" : "agente"}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => setShowNew((v) => !v)}
          className="border-accent text-accent hover:border-accent/70 hover:text-accent/70 inline-flex items-center gap-1.5 rounded border px-3 py-1 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors"
        >
          <Plus className="h-3 w-3" />
          Novo agente
        </button>
      </div>

      {/* Filters + inline create */}
      <div className="border-border flex flex-col gap-2 border-b px-6 py-3">
        {showNew && <NewAgentInline onCancel={() => setShowNew(false)} />}
        <div className="flex gap-2">
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
      </div>

      {/* Content */}
      <div className="px-6 py-4">
        {isPending ? (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <span className="sr-only">Carregando…</span>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="border-border bg-card h-20 animate-pulse rounded border" />
            ))}
          </div>
        ) : isError ? (
          <p className="text-destructive text-[13px]">Erro ao carregar agentes.</p>
        ) : data.items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-12">
            <p className="text-muted-foreground text-[13px]">Nenhum agente encontrado</p>
            {!q && !status && (
              <p className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
                Clique em &quot;Novo agente&quot; para começar
              </p>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {data.items.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="border-border text-muted-foreground mt-4 flex items-center justify-end gap-2 border-t pt-3 text-[13px]">
            <button
              type="button"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="hover:text-foreground p-1 transition-colors disabled:opacity-40"
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
              className="hover:text-foreground p-1 transition-colors disabled:opacity-40"
              aria-label="Próxima página"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
