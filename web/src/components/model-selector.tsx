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
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 transition-colors focus:border-zinc-400 focus:outline-none disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500";

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
      <div className="flex flex-col gap-1.5">
        <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Modelo<span className="ml-0.5 text-red-500">*</span>
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
        {error && <p className="text-xs text-red-500">{error}</p>}
      </div>

      {supported && (
        <fieldset className="rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 dark:border-zinc-700 dark:bg-zinc-800/50">
          <legend className="px-1 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Capabilities
          </legend>
          <div className="mt-2 flex flex-col gap-2">
            {(Object.keys(CAP_LABELS) as (keyof CapabilityFlags)[]).map((key) => (
              <label
                key={key}
                className={`flex items-center gap-2 text-sm transition-colors ${
                  supported[key]
                    ? "cursor-pointer text-zinc-700 dark:text-zinc-300"
                    : "cursor-not-allowed text-zinc-400 dark:text-zinc-600"
                }`}
              >
                <input
                  type="checkbox"
                  checked={supported[key] ? capabilities[key] : false}
                  onChange={(e) => handleCapabilityChange(key, e.target.checked)}
                  disabled={!supported[key]}
                  className="h-4 w-4"
                />
                {CAP_LABELS[key]}
                {!supported[key] && (
                  <span className="text-xs text-zinc-400 dark:text-zinc-600">(não suportado)</span>
                )}
              </label>
            ))}
          </div>
        </fieldset>
      )}
    </div>
  );
}
