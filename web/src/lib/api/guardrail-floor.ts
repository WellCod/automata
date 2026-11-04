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
      const path = { params: { path: { config_id: configId! } } } as const;
      let res = await client.GET("/api/v1/configs/{config_id}/guardrails/effective", {
        params: { path: { config_id: configId! }, query: { draft: true } },
      });
      // sem rascunho, o piso é o mesmo: lê pela versão publicada
      if (res.error)
        res = await client.GET("/api/v1/configs/{config_id}/guardrails/effective", path);
      if (res.error) return null;
      return res.data.floor ?? null;
    },
  });
}
