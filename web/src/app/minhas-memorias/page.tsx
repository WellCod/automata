"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";

/** O que os agentes lembram de quem está logado, com apagar (ADR-0025). */
export default function MyMemoriesPage() {
  const queryClient = useQueryClient();
  const { data, isPending, isError } = useQuery({
    queryKey: ["my-memories"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/me/memories");
      if (!result.data) throw new Error("Falha ao carregar");
      return result.data;
    },
  });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["my-memories"] });
  const removeOne = useMutation({
    mutationFn: async (memoryId: string) => {
      const result = await client.DELETE("/api/v1/me/memories/{memory_id}", {
        params: { path: { memory_id: memoryId } },
      });
      if (result.error) throw new Error(apiErrorMessage(result.error, "Falha ao apagar"));
    },
    onSuccess: refresh,
    onError: (e) => toast.error(e.message),
  });
  const forgetAll = useMutation({
    mutationFn: async () => {
      const result = await client.DELETE("/api/v1/me/memories");
      if (!result.response.ok) throw new Error("Falha ao apagar");
    },
    onSuccess: () => {
      toast.success("Memórias apagadas");
      refresh();
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="flex max-w-3xl flex-col gap-4 p-6">
      <div>
        <h1 className="text-foreground flex items-center gap-2 text-[18px] font-semibold">
          <Brain className="h-4 w-4" /> Minhas memórias
        </h1>
        <p className="text-muted-foreground text-[13px]">
          O que os agentes com memória lembram de você das conversas pelo painel. Cada agente só lê
          o que ele mesmo guardou.
        </p>
      </div>
      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar as memórias.
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhum agente guardou memória sua.</p>
      )}
      {data && data.length > 0 && (
        <>
          <ul aria-label="Memórias" className="border-border bg-card rounded border px-3">
            {data.map((memory) => (
              <li
                key={memory.memory_id}
                className="border-border flex items-start justify-between gap-2 border-b py-2 text-[13px] last:border-b-0"
              >
                <span className="text-foreground">
                  {memory.memory}
                  <span className="text-muted-foreground text-[11px]">
                    {" "}
                    · {memory.agent_name ?? "agente removido"}
                  </span>
                </span>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => removeOne.mutate(memory.memory_id)}
                >
                  Apagar
                </Button>
              </li>
            ))}
          </ul>
          <div>
            <Button
              size="sm"
              variant="destructive"
              disabled={forgetAll.isPending}
              onClick={() => {
                if (window.confirm("Apagar tudo o que os agentes lembram de você?"))
                  forgetAll.mutate();
              }}
            >
              Apagar todas
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
