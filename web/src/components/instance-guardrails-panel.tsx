"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import {
  DEFAULT_GUARDRAILS,
  type Guardrails,
  GuardrailsEditor,
  guardrailProblems,
  withDefaults,
} from "@/components/guardrails-editor";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";

const KEY = ["instance-guardrails"];

export function useInstanceGuardrails() {
  return useQuery({
    queryKey: KEY,
    queryFn: async () => {
      const res = await client.GET("/api/v1/instance-guardrails");
      if (res.error)
        throw new Error("Falha ao carregar o piso de guardrails. Apenas owners têm acesso.");
      return res.data;
    },
  });
}

function FloorForm({
  initial,
  saved,
  updatedBy,
}: {
  initial: Guardrails;
  saved: boolean;
  updatedBy: string | null | undefined;
}) {
  const queryClient = useQueryClient();
  const [value, setValue] = useState<Guardrails>(initial);
  const problems = guardrailProblems(withDefaults(value));
  const put = useMutation({
    mutationFn: async (settings: Guardrails | null) => {
      const res = await client.PUT("/api/v1/instance-guardrails", { body: { settings } });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o piso"));
      return res.data;
    },
    onSuccess: (data) => {
      toast.success(data.settings ? "Piso salvo. Vale no próximo run." : "Piso removido.");
      if (!data.settings) setValue(DEFAULT_GUARDRAILS);
      void queryClient.invalidateQueries({ queryKey: KEY });
      void queryClient.invalidateQueries({ queryKey: ["guardrail-floor"] });
    },
    onError: (e) => toast.error(e.message),
  });
  const costly = value.moderation || value.classifier || value.output?.classifier;
  return (
    <div className="flex flex-col gap-3">
      <GuardrailsEditor value={value} onChange={setValue} instance />
      {costly && (
        <p className="text-[12px] text-amber-600 dark:text-amber-400">
          Moderação e classificador no piso fazem uma chamada a mais por mensagem em todos os
          agentes da instância.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="strong"
          disabled={problems.length > 0 || put.isPending}
          onClick={() => put.mutate(value)}
        >
          Salvar piso
        </Button>
        {saved && (
          <Button
            variant="subtleDestructive"
            disabled={put.isPending}
            onClick={() => put.mutate(null)}
          >
            Remover piso
          </Button>
        )}
        {updatedBy && (
          <span className="text-muted-foreground text-[12px]">Alterado por {updatedBy}</span>
        )}
      </div>
    </div>
  );
}

export function InstanceGuardrailsPanel() {
  const { data, error, isLoading } = useInstanceGuardrails();
  if (isLoading) return <p className="text-muted-foreground text-[13px]">Carregando…</p>;
  if (error) return <p className="text-destructive text-[13px]">{error.message}</p>;
  return (
    <FloorForm
      // remonta com o valor gravado quando ele chega ou muda
      key={data?.updated_at ?? "vazio"}
      initial={withDefaults(data?.settings ?? DEFAULT_GUARDRAILS)}
      saved={data?.settings != null}
      updatedBy={data?.updated_by}
    />
  );
}
