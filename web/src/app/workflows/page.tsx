"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Workflow } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { SuiteBadge } from "@/components/suite-badge";
import { useSuiteStatus } from "@/lib/api/evals";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/status-badge";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

function NewWorkflowForm({ onCancel }: { onCancel: () => void }) {
  const id = useId();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const create = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/configs", {
        body: { name: name.trim(), description: description.trim(), kind: "workflow" },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao criar workflow"));
      return res.data!;
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      router.push(`/workflows/${data.id}`);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && description.trim()) create.mutate();
      }}
      className="border-border bg-card flex flex-col gap-3 rounded border p-4"
      aria-label="Novo workflow"
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
          placeholder="Em que situação usar este workflow"
          className={inputCls}
        />
      </div>
      {create.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} variant="muted">
          Cancelar
        </Button>
        <Button
          type="submit"
          disabled={create.isPending || !name.trim() || !description.trim()}
          variant="strong"
        >
          {create.isPending ? "Criando…" : "Criar"}
        </Button>
      </div>
    </form>
  );
}

export default function WorkflowsPage() {
  const [showNew, setShowNew] = useState(false);
  const { data: suites } = useSuiteStatus();
  const { data, isPending, isError } = useQuery({
    queryKey: ["configs", "workflows"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs", {
        params: { query: { kind: "workflow", page_size: 100 } },
      });
      if (res.error) throw new Error("Falha ao carregar workflows");
      return res.data!;
    },
  });

  return (
    <div className="w-full px-6 py-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-foreground text-sm font-medium">Workflows</h1>
          <p className="text-muted-foreground mt-0.5 text-[13px]">
            Etapas em ordem fixa, com paralelos, condições e repetições.
          </p>
        </div>
        <Button onClick={() => setShowNew(true)} variant="accent">
          <Plus className="h-3.5 w-3.5" aria-hidden />
          Novo workflow
        </Button>
      </div>

      {showNew && (
        <div className="mb-4">
          <NewWorkflowForm onCancel={() => setShowNew(false)} />
        </div>
      )}

      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Erro ao carregar workflows.
        </p>
      )}
      {data && data.items.length === 0 && !showNew && (
        <div className="border-border flex flex-col items-center gap-3 rounded border border-dashed px-6 py-12 text-center">
          <Workflow className="text-accent h-5 w-5" aria-hidden />
          <p className="text-foreground text-sm">Nenhum workflow ainda</p>
          <p className="text-muted-foreground max-w-md text-[13px]">
            Publique os agentes e times de cada etapa e monte a ordem: triagem, análises em
            paralelo, uma condição e a resposta final.
          </p>
        </div>
      )}
      {data && data.items.length > 0 && (
        <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((wf) => (
            <li key={wf.id}>
              <Link
                href={`/workflows/${wf.id}`}
                className="border-border bg-card hover:border-accent flex h-full flex-col gap-1 rounded border p-4 transition-colors"
              >
                <span className="text-foreground text-sm font-medium">{wf.name}</span>
                <span className="text-muted-foreground line-clamp-2 text-[13px]">
                  {wf.description}
                </span>
                <span className="mt-auto flex flex-wrap gap-1 pt-2">
                  {wf.current_version ? (
                    <Badge tone="active">v{wf.current_version.version_number} ativa</Badge>
                  ) : wf.draft_version ? (
                    <Badge tone="pending">Rascunho</Badge>
                  ) : (
                    <Badge tone="neutral">Sem versão</Badge>
                  )}
                  <SuiteBadge status={suites?.get(wf.id)} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
