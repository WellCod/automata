"use client";

import type { components } from "@/lib/api/schema.d.ts";

export type Memory = components["schemas"]["MemorySettings"];

export const DEFAULT_MEMORY: Memory = { enabled: false, instructions: null, retention_days: 90 };

export function withMemoryDefaults(value: Partial<Memory> | undefined): Memory {
  return { ...DEFAULT_MEMORY, ...(value ?? {}) };
}

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

const RETENTION = [30, 90, 180, 365];

export function MemoryEditor({
  value,
  onChange,
}: {
  value: Memory;
  onChange: (v: Memory) => void;
}) {
  return (
    <fieldset className="border-border flex flex-col gap-2 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">Memória do usuário</legend>
      <label className="text-foreground flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
        />
        Lembrar do usuário entre conversas
      </label>
      <p className="text-muted-foreground text-[12px]">
        No fim de cada conversa, o modelo do agente guarda fatos que o usuário contou. Só este
        agente lê o que guardou, e só para o mesmo usuário. Documento, cartão e e-mail saem
        mascarados, e conversa sem usuário identificado não gera memória.
      </p>
      {value.enabled && (
        <div className="flex flex-col gap-2">
          <textarea
            aria-label="O que lembrar"
            value={value.instructions ?? ""}
            maxLength={500}
            rows={2}
            placeholder="Ex.: tamanho que veste, preferência de horário de entrega"
            onChange={(e) => onChange({ ...value, instructions: e.target.value || null })}
            className={`${inputCls} resize-y`}
          />
          <label className="text-muted-foreground flex items-center gap-1 text-[12px]">
            Apagar depois de
            <select
              value={value.retention_days}
              onChange={(e) => onChange({ ...value, retention_days: Number(e.target.value) })}
              className={inputCls}
            >
              {RETENTION.map((d) => (
                <option key={d} value={d}>
                  {d} dias sem uso
                </option>
              ))}
            </select>
          </label>
          <p className="text-muted-foreground text-[11px]">
            Memória é dado pessoal: avise os usuários que o atendimento lembra do que eles contam.
          </p>
        </div>
      )}
    </fieldset>
  );
}
