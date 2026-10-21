"use client";

import type { components } from "@/lib/api/schema.d.ts";

export type Conversation = components["schemas"]["ConversationSettings"];

export const DEFAULT_CONVERSATION: Conversation = {
  compaction: false,
  compact_at_tokens: 16_000,
  keep_recent_runs: 3,
  summary_instructions: null,
  search_history: true,
};

export function withConversationDefaults(value: Partial<Conversation> | undefined): Conversation {
  return { ...DEFAULT_CONVERSATION, ...(value ?? {}) };
}

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none";

// ~4 caracteres por token em português: a referência ajuda a escolher o limite
function pages(tokens: number): string {
  return `~${Math.round((tokens * 4) / 3000)} páginas de texto`;
}

export function ConversationEditor({
  value,
  onChange,
}: {
  value: Conversation;
  onChange: (v: Conversation) => void;
}) {
  return (
    <fieldset className="border-border flex flex-col gap-2 rounded border px-4 pt-3 pb-4">
      <legend className="px-1 text-[13px] font-medium">Conversa longa</legend>
      <label className="text-foreground flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={value.compaction}
          onChange={(e) => onChange({ ...value, compaction: e.target.checked })}
        />
        Resumir os turnos antigos quando a conversa ficar grande
      </label>
      <p className="text-muted-foreground text-[12px]">
        Sem isto, o agente leva os últimos 5 turnos inteiros e esquece o começo da conversa. Com
        isto, o que passar do limite vira um resumo feito pelo próprio modelo do agente, cobrado no
        consumo dele.
      </p>
      {value.compaction && (
        <div className="flex flex-col gap-2">
          <div className="text-muted-foreground flex flex-wrap items-center gap-3 text-[12px]">
            <label className="flex items-center gap-1">
              Resumir a partir de
              <input
                type="number"
                aria-label="Limite em tokens"
                min={4000}
                max={128000}
                step={1000}
                value={value.compact_at_tokens}
                onChange={(e) => onChange({ ...value, compact_at_tokens: Number(e.target.value) })}
                className={`${inputCls} w-24`}
              />
              tokens ({pages(value.compact_at_tokens)})
            </label>
            <label className="flex items-center gap-1">
              Manter inteiros os últimos
              <input
                type="number"
                aria-label="Turnos mantidos inteiros"
                min={1}
                max={20}
                value={value.keep_recent_runs}
                onChange={(e) => onChange({ ...value, keep_recent_runs: Number(e.target.value) })}
                className={`${inputCls} w-14`}
              />
              turnos
            </label>
          </div>
          <input
            aria-label="O que o resumo não pode perder"
            value={value.summary_instructions ?? ""}
            maxLength={500}
            placeholder="O que o resumo não pode perder, ex.: números de pedido e prazos combinados"
            onChange={(e) => onChange({ ...value, summary_instructions: e.target.value || null })}
            className={inputCls}
          />
          <label className="text-muted-foreground flex items-center gap-2 text-[12px]">
            <input
              type="checkbox"
              checked={value.search_history}
              onChange={(e) => onChange({ ...value, search_history: e.target.checked })}
            />
            Deixar o agente buscar no histórico resumido um detalhe que o resumo deixou de fora
          </label>
        </div>
      )}
    </fieldset>
  );
}
