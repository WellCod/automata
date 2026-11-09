import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type Guardrails = components["schemas"]["GuardrailSettings"];

/** Piso da instância que o config herda (ADR-0034); quem não é owner também lê por aqui. */
export function useGuardrailFloor(configId: string | undefined) {
  return useQuery({
    queryKey: ["guardrail-floor", configId],
    enabled: !!configId,
    queryFn: async (): Promise<Guardrails | null> => {
      // sem rascunho, a API responde pela versão publicada
      const res = await client.GET("/api/v1/configs/{config_id}/guardrails/effective", {
        params: { path: { config_id: configId! }, query: { draft: true } },
      });
      if (res.error) return null;
      return res.data.floor ?? null;
    },
  });
}
