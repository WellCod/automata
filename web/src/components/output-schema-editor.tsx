"use client";

import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";
import client from "@/lib/api/client";
import type { CapabilityFlags } from "@/components/model-selector";

export type OutputSchema = Record<string, unknown>;

export const EXAMPLE_SCHEMA: OutputSchema = {
  type: "object",
  properties: {
    categoria: { type: "string", enum: ["troca", "reembolso", "duvida"] },
    resumo: { type: "string" },
  },
  required: ["categoria", "resumo"],
  additionalProperties: false,
};

// a API confere o resto (Draft 2020-12, 32 KB); aqui só o que dá para dizer na hora
export function parseSchema(text: string): { schema: OutputSchema | null; error: string | null } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    return { schema: null, error: "JSON inválido" };
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed))
    return { schema: null, error: "O schema precisa ser um objeto JSON" };
  if ((parsed as OutputSchema).type !== "object")
    return { schema: null, error: 'A raiz precisa ter "type": "object"' };
  return { schema: parsed as OutputSchema, error: null };
}

export function OutputSchemaEditor({
  value,
  onChange,
  modelId,
}: {
  value: OutputSchema | null;
  // null desliga; a página acompanha a capability structured_output
  onChange: (v: OutputSchema | null) => void;
  modelId: string;
}) {
  const id = useId();
  const { data: models } = useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, CapabilityFlags>;
    },
  });
  const supported = models?.[modelId]?.structured_output ?? false;
  const [text, setText] = useState(() => JSON.stringify(value ?? EXAMPLE_SCHEMA, null, 2));
  const [error, setError] = useState<string | null>(null);
  // a versão chega depois da montagem: o texto acompanha o valor que veio de fora
  const [shown, setShown] = useState(value);
  if (value !== shown) {
    setShown(value);
    if (value) setText(JSON.stringify(value, null, 2));
  }
  const on = value != null;

  return (
    <fieldset className="border-border flex flex-col gap-2 rounded border px-4 pt-3 pb-4">
      <legend className="px-1 text-[13px] font-medium">Saída estruturada</legend>
      <label className="text-foreground flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={on}
          disabled={!supported && !on}
          onChange={(e) => {
            if (!e.target.checked) return onChange(null);
            const parsed = parseSchema(text);
            setError(parsed.error);
            onChange(parsed.schema ?? EXAMPLE_SCHEMA);
          }}
        />
        Responder em JSON no formato de um schema
        {!supported && (
          <span className="text-muted-foreground text-[11px]">(modelo sem suporte)</span>
        )}
      </label>
      <p className="text-muted-foreground text-[12px]">
        Para quem integra pela API ou por MCP e precisa de campos fixos, como categoria e valor. A
        resposta deixa de ser texto livre. Mudar o schema muda o contrato com quem integra.
      </p>
      {on && (
        <>
          <label htmlFor={id} className="text-foreground text-[12px]">
            JSON Schema
          </label>
          <textarea
            id={id}
            value={text}
            rows={12}
            spellCheck={false}
            aria-invalid={error != null}
            onChange={(e) => setText(e.target.value)}
            onBlur={() => {
              const parsed = parseSchema(text);
              setError(parsed.error);
              if (parsed.schema) onChange(parsed.schema);
            }}
            className="border-border text-foreground focus:border-accent w-full rounded border bg-[var(--input)] px-3 py-2 font-mono text-[12px] focus:outline-none"
          />
          {error && (
            <p className="text-destructive text-[12px]" role="alert">
              {error}
            </p>
          )}
        </>
      )}
    </fieldset>
  );
}
