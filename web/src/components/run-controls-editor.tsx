"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import type { CapabilityFlags } from "@/components/model-selector";

export type RunControls = components["schemas"]["RunControls"];

export const DEFAULT_RUN: RunControls = {
  tool_call_limit: null,
  provider_retries: 0,
  fallback_models: [],
};

export function withRunDefaults(value: Partial<RunControls> | undefined): RunControls {
  return { ...DEFAULT_RUN, ...(value ?? {}) };
}

const CAP_NAMES: Record<keyof CapabilityFlags, string> = {
  extended_thinking: "pensamento estendido",
  structured_output: "saída estruturada",
  vision: "visão",
};

// mesma regra de ConfigService._fallback_errors: a reserva faz tudo o que o agente liga
export function missingCapabilities(
  candidate: CapabilityFlags | undefined,
  wanted: CapabilityFlags,
): string[] {
  if (!candidate) return [];
  return (Object.keys(CAP_NAMES) as (keyof CapabilityFlags)[])
    .filter((k) => wanted[k] && !candidate[k])
    .map((k) => CAP_NAMES[k]);
}

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground focus:border-accent focus:outline-none";

export function RunControlsEditor({
  value,
  onChange,
  modelId,
  capabilities,
}: {
  value: RunControls;
  onChange: (v: RunControls) => void;
  modelId: string;
  capabilities: CapabilityFlags;
}) {
  const { data: models } = useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, CapabilityFlags>;
    },
  });
  const fallbacks = value.fallback_models ?? [];
  const limited = value.tool_call_limit != null;

  function setFallback(i: number, modelId: string) {
    const next = [...fallbacks];
    if (modelId) next[i] = modelId;
    else next.splice(i, 1);
    onChange({ ...value, fallback_models: next.filter(Boolean) });
  }

  return (
    <fieldset className="border-border flex flex-col gap-3 rounded border px-4 pt-3 pb-4">
      <legend className="px-1 text-[13px] font-medium">Controle do run</legend>

      <div className="flex flex-col gap-1">
        <label className="text-foreground flex flex-wrap items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            checked={limited}
            onChange={(e) => onChange({ ...value, tool_call_limit: e.target.checked ? 10 : null })}
          />
          Limitar chamadas de tool por run
          {limited && (
            <input
              type="number"
              aria-label="Máximo de chamadas de tool"
              min={1}
              max={100}
              value={value.tool_call_limit ?? 10}
              onChange={(e) => onChange({ ...value, tool_call_limit: Number(e.target.value) })}
              className={`${inputCls} w-16`}
            />
          )}
        </label>
        <p className="text-muted-foreground text-[12px]">
          Corta o laço de um modelo que chama a mesma tool sem parar. Passado o limite, a tool não
          roda e o modelo responde com o que já tem.
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label className="text-foreground flex flex-wrap items-center gap-2 text-[13px]">
          Repetir a chamada ao provedor quando ele falhar
          <select
            aria-label="Tentativas extras no provedor"
            value={value.provider_retries ?? 0}
            onChange={(e) => onChange({ ...value, provider_retries: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={0}>não repetir</option>
            <option value={1}>1 vez</option>
            <option value={2}>2 vezes</option>
            <option value={3}>3 vezes</option>
          </select>
        </label>
        <p className="text-muted-foreground text-[12px]">
          Vale para erro 5xx, 429 e falha de rede, com espera de 1, 2 e 4 s. Só a chamada ao modelo
          se repete: tool que já rodou não roda de novo.
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-foreground text-[13px]">Modelos reserva</span>
        {[0, 1].map((i) => {
          if (i > fallbacks.length) return null;
          const current = fallbacks[i] ?? "";
          return (
            <select
              key={i}
              aria-label={`Modelo reserva ${i + 1}`}
              value={current}
              onChange={(e) => setFallback(i, e.target.value)}
              className={`${inputCls} max-w-full min-w-0 sm:w-72`}
            >
              <option value="">{i === 0 ? "Sem reserva" : "Sem segunda reserva"}</option>
              {Object.entries(models ?? {})
                .filter(([id]) => id !== modelId)
                .map(([id, caps]) => {
                  const missing = missingCapabilities(caps, capabilities);
                  const taken = fallbacks.includes(id) && id !== current;
                  return (
                    <option key={id} value={id} disabled={missing.length > 0 || taken}>
                      {id}
                      {missing.length > 0 ? ` (sem ${missing.join(", ")})` : ""}
                    </option>
                  );
                })}
            </select>
          );
        })}
        <p className="text-muted-foreground text-[12px]">
          Usados em ordem quando o modelo principal falha de vez ou responde 429. Credencial errada
          (401, 403) não troca de modelo. A reserva é cobrada pelo preço dela.
        </p>
      </div>
    </fieldset>
  );
}
