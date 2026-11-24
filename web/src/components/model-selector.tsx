"use client";

import { useQuery } from "@tanstack/react-query";
import client from "@/lib/api/client";

export type CapabilityFlags = {
  extended_thinking: boolean;
  structured_output: boolean;
  vision: boolean;
};

interface Props {
  value: string;
  capabilities: CapabilityFlags;
  onChange: (modelId: string, caps: CapabilityFlags) => void;
  error?: string;
}

const CAP_LABELS: Record<keyof CapabilityFlags, string> = {
  extended_thinking: "Pensamento estendido",
  structured_output: "Saída estruturada",
  vision: "Visão",
};

const EMPTY_CAPS: CapabilityFlags = {
  extended_thinking: false,
  structured_output: false,
  vision: false,
};

const selectCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground transition-colors focus:border-accent focus:outline-none disabled:opacity-40";

export function ModelSelector({ value, capabilities, onChange, error }: Props) {
  const { data: models, isPending } = useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const response = await client.GET("/api/v1/models/capabilities");
      if (response.error) throw new Error("Falha ao carregar modelos");
      return response.data as Record<string, CapabilityFlags>;
    },
  });

  // provedor sem chave no ambiente: o run falharia na hora (UX-03)
  const { data: available } = useQuery({
    queryKey: ["models:availability"],
    queryFn: async () => {
      const response = await client.GET("/api/v1/models/availability");
      if (response.error) return {} as Record<string, boolean>;
      return response.data as Record<string, boolean>;
    },
  });
  const ready = (id: string) => available?.[id] !== false;

  const supported: CapabilityFlags | null = (value && models?.[value]) || null;

  const handleModelChange = (newModelId: string) => {
    const newSupported = (newModelId && models?.[newModelId]) || EMPTY_CAPS;
    onChange(newModelId, {
      extended_thinking: capabilities.extended_thinking && newSupported.extended_thinking,
      structured_output: capabilities.structured_output && newSupported.structured_output,
      vision: capabilities.vision && newSupported.vision,
    });
  };

  const handleCapabilityChange = (key: keyof CapabilityFlags, checked: boolean) => {
    onChange(value, { ...capabilities, [key]: checked });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label className="text-foreground text-[13px] font-medium">
          Modelo<span className="text-destructive ml-0.5">*</span>
        </label>
        <select
          aria-label="Modelo"
          value={value}
          onChange={(e) => handleModelChange(e.target.value)}
          disabled={isPending}
          className={selectCls}
        >
          <option value="">{isPending ? "Carregando modelos…" : "Selecione um modelo"}</option>
          {Object.keys(models ?? {}).map((id) => (
            <option key={id} value={id} disabled={!ready(id) && id !== value}>
              {ready(id) ? id : `${id} (sem chave do provedor)`}
            </option>
          ))}
        </select>
        {value && !ready(value) && (
          <p className="text-[11px] text-amber-700 dark:text-amber-400">
            Este modelo não tem a chave do provedor configurada na instância: o agente não vai
            responder. Escolha outro ou peça a chave a quem administra.
          </p>
        )}
        {error && <p className="text-destructive text-[11px]">{error}</p>}
      </div>

      {supported && (
        <fieldset className="border-border bg-muted rounded border px-4 py-3">
          <legend className="text-muted-foreground px-1 text-[11px] font-medium">
            Capabilities
          </legend>
          <div className="mt-2 flex flex-col gap-2">
            {(Object.keys(CAP_LABELS) as (keyof CapabilityFlags)[]).map((key) => (
              <label
                key={key}
                className={`flex items-center gap-2 text-[13px] ${
                  supported[key]
                    ? "text-foreground cursor-pointer"
                    : "text-muted-foreground cursor-not-allowed"
                }`}
              >
                <input
                  type="checkbox"
                  checked={supported[key] ? capabilities[key] : false}
                  onChange={(e) => handleCapabilityChange(key, e.target.checked)}
                  disabled={!supported[key]}
                  className="h-3.5 w-3.5 accent-[var(--accent)]"
                />
                {CAP_LABELS[key]}
                {!supported[key] && (
                  <span className="text-muted-foreground text-[11px]">(não suportado)</span>
                )}
              </label>
            ))}
          </div>
        </fieldset>
      )}
    </div>
  );
}
