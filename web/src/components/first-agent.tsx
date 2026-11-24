"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";

// instância vazia: três passos e agentes de exemplo para não começar do zero (UX-02)
export function FirstAgent({ onNew }: { onNew: () => void }) {
  const router = useRouter();
  const { data: templates } = useQuery({
    queryKey: ["templates"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/templates");
      if (result.error) return [];
      return result.data!;
    },
  });
  const create = useMutation({
    mutationFn: async (key: string) => {
      const result = await client.POST("/api/v1/templates/{key}", { params: { path: { key } } });
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Falha ao criar a partir do exemplo"));
      return result.data!;
    },
    onSuccess: (data) => router.push(`/agents/${data.id}`),
    onError: (e) => toast.error(e.message),
  });

  return (
    <div className="border-border flex flex-col gap-5 rounded border p-6">
      <div>
        <h2 className="text-foreground text-[15px] font-medium">Seu primeiro agente</h2>
        <ol className="text-muted-foreground mt-2 list-decimal pl-5 text-[13px] leading-6">
          <li>Crie um agente do zero ou a partir de um exemplo abaixo.</li>
          <li>Escolha o modelo e escreva as instruções; salve o rascunho.</li>
          <li>Converse com ele no modo teste e publique quando estiver bom.</li>
        </ol>
      </div>
      <Button onClick={onNew} variant="strong" className="self-start">
        Criar do zero
      </Button>
      {templates && templates.length > 0 && (
        <div className="flex flex-col gap-2">
          <h3 className="text-foreground text-[13px] font-medium">Ou comece de um exemplo</h3>
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <li
                key={template.key}
                className="border-border bg-card flex flex-col gap-2 rounded border p-3"
              >
                <span className="text-foreground text-[13px] font-medium">{template.name}</span>
                <span className="text-muted-foreground text-[12px]">{template.description}</span>
                <Button
                  size="sm"
                  variant="muted"
                  className="mt-auto self-start"
                  disabled={create.isPending}
                  onClick={() => create.mutate(template.key)}
                  aria-label={`Criar a partir de ${template.name}`}
                >
                  Usar este exemplo
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
