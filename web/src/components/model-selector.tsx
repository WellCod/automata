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
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, CapabilityFlags>;
    },
  });

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
          value={value}
          onChange={(e) => handleModelChange(e.target.value)}
          disabled={isPending}
          className={selectCls}
        >
          <option value="">{isPending ? "Carregando modelos…" : "Selecione um modelo"}</option>
          {Object.keys(models ?? {}).map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        {error && <p className="text-destructive text-[11px]">{error}</p>}
      </div>

      {supported && (
        <fieldset className="border-border bg-muted rounded border px-4 py-3">
          <legend className="text-muted-foreground px-1 text-[11px] font-medium tracking-[0.05em] uppercase">
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
