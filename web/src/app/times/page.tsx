"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";

const btnCls =
  "inline-flex h-7 items-center gap-1.5 rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40";
const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function NewTeamForm({ onCancel }: { onCancel: () => void }) {
  const id = useId();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/configs", {
        body: { name: name.trim(), description: description.trim(), kind: "team" },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao criar time"));
      return res.data!;
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      router.push(`/times/${data.id}`);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && description.trim()) create.mutate();
      }}
      className="border-border bg-card flex flex-col gap-3 rounded border p-4"
      aria-label="Novo time"
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-name`} className="text-foreground text-[13px] font-medium">
          Nome
        </label>
        <input
          id={`${id}-name`}
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={inputCls}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-desc`} className="text-foreground text-[13px] font-medium">
          Descrição
        </label>
        <input
          id={`${id}-desc`}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Em que situação usar este time"
          className={inputCls}
        />
      </div>
      {create.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className={`${btnCls} border-border text-muted-foreground hover:text-foreground`}
        >
          Cancelar
        </button>
        <button
          type="submit"
          disabled={create.isPending || !name.trim() || !description.trim()}
          className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
        >
          {create.isPending ? "Criando…" : "Criar"}
        </button>
      </div>
    </form>
  );
}

export default function TeamsPage() {
  const [showNew, setShowNew] = useState(false);
  const { data, isPending, isError } = useQuery({
    queryKey: ["configs", "teams"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs", {
        params: { query: { kind: "team", page_size: 100 } },
      });
      if (res.error) throw new Error("Falha ao carregar times");
      return res.data!;
    },
  });

  return (
    <div className="w-full px-6 py-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-foreground text-sm font-medium">Times</h1>
          <p className="text-muted-foreground mt-0.5 text-[13px]">
            Um líder que delega a agentes especialistas.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowNew(true)}
          className={`${btnCls} border-accent text-accent hover:border-foreground hover:text-foreground`}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          Novo time
        </button>
      </div>

      {showNew && (
        <div className="mb-4">
          <NewTeamForm onCancel={() => setShowNew(false)} />
        </div>
      )}

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Erro ao carregar times.
        </p>
      )}
      {data && data.items.length === 0 && !showNew && (
        <div className="border-border flex flex-col items-center gap-3 rounded border border-dashed px-6 py-12 text-center">
          <Users className="text-accent h-5 w-5" aria-hidden />
          <p className="text-foreground text-sm">Nenhum time ainda</p>
          <p className="text-muted-foreground max-w-md text-[13px]">
            Publique os agentes especialistas, crie um time e escolha como o líder coordena:
            delegando, roteando para um só ou consultando todos.
          </p>
        </div>
      )}
      {data && data.items.length > 0 && (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((team) => (
            <li key={team.id}>
              <Link
                href={`/times/${team.id}`}
                className="border-border bg-card hover:border-accent flex h-full flex-col gap-1 rounded border p-4 transition-colors"
              >
                <span className="text-foreground text-sm font-medium">{team.name}</span>
                <span className="text-muted-foreground line-clamp-2 text-[13px]">
                  {team.description}
                </span>
                <span className="text-muted-foreground mt-auto pt-2 text-[11px] tracking-[0.05em] uppercase">
                  {team.current_version
                    ? `v${team.current_version.version_number} ativo`
                    : team.draft_version
                      ? "rascunho"
                      : "sem versão"}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
