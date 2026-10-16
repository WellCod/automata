"use client";

import { useId } from "react";
import type { components } from "@/lib/api/schema.d.ts";

export type Guardrails = components["schemas"]["GuardrailSettings"];
type PiiType = NonNullable<NonNullable<Guardrails["pii"]>["types"]>[number];

export const PII_LABELS: Record<PiiType, string> = {
  cpf: "CPF",
  cnpj: "CNPJ",
  cartao: "Cartão",
  email: "E-mail",
  telefone: "Telefone",
};
const PII_TYPES = Object.keys(PII_LABELS) as PiiType[];

type PiiRule = NonNullable<Guardrails["pii"]>;
type OutputRule = NonNullable<Guardrails["output"]>;
const DEFAULT_PII: PiiRule = { mode: "off", types: PII_TYPES };
const DEFAULT_OUTPUT: OutputRule = { pii: false, pii_types: PII_TYPES, blocked_terms: [] };

export const DEFAULT_GUARDRAILS: Guardrails = {
  pii: DEFAULT_PII,
  prompt_injection: false,
  injection_extra_terms: [],
  blocked_topics: [],
  max_input_chars: null,
  moderation: false,
  output: DEFAULT_OUTPUT,
  blocked_message: "Não posso ajudar com essa mensagem por aqui.",
};

// o payload salvo pode vir sem alguma seção (versões anteriores aos guardrails)
export function withDefaults(g: Partial<Guardrails> | null | undefined): Guardrails {
  return {
    ...DEFAULT_GUARDRAILS,
    ...g,
    pii: { ...DEFAULT_PII, ...g?.pii },
    output: { ...DEFAULT_OUTPUT, ...g?.output },
  };
}

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";
const hintCls = "text-muted-foreground text-[11px]";
const checkCls = "h-3.5 w-3.5 accent-[var(--accent)]";

function lines(value: string): string[] {
  return value
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

function TermsField({
  id,
  label,
  hint,
  value,
  onChange,
}: {
  id: string;
  label: string;
  hint: string;
  value: string[];
  onChange: (v: string[]) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-foreground text-[13px]">
        {label}
      </label>
      <textarea
        id={id}
        rows={3}
        defaultValue={value.join("\n")}
        onBlur={(e) => onChange(lines(e.target.value))}
        className={`${inputCls} resize-y`}
        placeholder="um por linha"
      />
      <span className={hintCls}>{hint}</span>
    </div>
  );
}

function PiiTypes({
  value,
  onChange,
  label,
}: {
  value: PiiType[];
  onChange: (v: PiiType[]) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-x-4 gap-y-1">
      {PII_TYPES.map((t) => (
        <label key={t} className="text-foreground flex items-center gap-1.5 text-[13px]">
          <input
            type="checkbox"
            className={checkCls}
            checked={value.includes(t)}
            onChange={(e) =>
              onChange(e.target.checked ? [...value, t] : value.filter((x) => x !== t))
            }
          />
          {PII_LABELS[t]}
        </label>
      ))}
    </div>
  );
}

export function GuardrailsEditor({
  value,
  onChange,
}: {
  value: Guardrails;
  onChange: (v: Guardrails) => void;
}) {
  const id = useId();
  const g = withDefaults(value);
  const pii = g.pii!;
  const output = g.output!;
  const set = (patch: Partial<Guardrails>) => onChange({ ...g, ...patch });

  return (
    <fieldset className="border-border flex flex-col gap-4 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">Guardrails</legend>
      <p className={hintCls}>
        Regras checadas antes de a mensagem chegar ao modelo: bloquear não gasta token. Valem a
        partir da próxima publicação, como as instruções.
      </p>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={`${id}-pii`} className="text-foreground text-[13px]">
          Dados pessoais na mensagem
        </label>
        <select
          id={`${id}-pii`}
          value={pii.mode}
          onChange={(e) => set({ pii: { ...pii, mode: e.target.value as typeof pii.mode } })}
          className={inputCls}
        >
          <option value="off">Não verificar</option>
          <option value="mask">Mascarar e seguir</option>
          <option value="block">Bloquear a mensagem</option>
        </select>
        {pii.mode !== "off" && (
          <PiiTypes
            label="Tipos de dado na entrada"
            value={pii.types ?? []}
            onChange={(types) => set({ pii: { ...pii, types } })}
          />
        )}
        <span className={hintCls}>
          CPF e CNPJ com dígito verificador e cartão com Luhn: número de pedido não é confundido.
          Mascarar troca o dado por “[CPF removido]” antes do modelo e da gravação.
        </span>
      </div>

      <label className="text-foreground flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          className={checkCls}
          checked={g.prompt_injection}
          onChange={(e) => set({ prompt_injection: e.target.checked })}
        />
        Bloquear tentativa de injeção de prompt (português e inglês)
      </label>
      {g.prompt_injection && (
        <TermsField
          id={`${id}-inj`}
          label="Termos extras de injeção"
          hint="Somam à lista padrão. De 3 a 100 caracteres cada."
          value={g.injection_extra_terms ?? []}
          onChange={(injection_extra_terms) => set({ injection_extra_terms })}
        />
      )}

      <TermsField
        id={`${id}-topics`}
        label="Tópicos proibidos"
        hint="A mensagem que contiver um destes termos é bloqueada (sem acento e sem maiúscula)."
        value={g.blocked_topics ?? []}
        onChange={(blocked_topics) => set({ blocked_topics })}
      />

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-max`} className="text-foreground text-[13px]">
          Tamanho máximo da mensagem (caracteres)
        </label>
        <input
          id={`${id}-max`}
          type="number"
          min={50}
          max={100000}
          value={g.max_input_chars ?? ""}
          placeholder="sem limite"
          onChange={(e) =>
            set({ max_input_chars: e.target.value === "" ? null : Number(e.target.value) })
          }
          className={inputCls}
        />
      </div>

      <label className="text-foreground flex items-start gap-2 text-[13px]">
        <input
          type="checkbox"
          className={`${checkCls} mt-0.5`}
          checked={g.moderation}
          onChange={(e) => set({ moderation: e.target.checked })}
        />
        <span className="flex flex-col gap-0.5">
          Moderação da OpenAI
          <span className={hintCls}>
            Uma chamada por mensagem, com o texto saindo da instância. Exige OPENAI_API_KEY na API.
          </span>
        </span>
      </label>

      <div className="border-border flex flex-col gap-2 border-t pt-3">
        <span className="text-foreground text-[13px] font-medium">Resposta do agente</span>
        <label className="text-foreground flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            className={checkCls}
            checked={output.pii ?? false}
            onChange={(e) => set({ output: { ...output, pii: e.target.checked } })}
          />
          Barrar resposta com dado pessoal
        </label>
        {output.pii && (
          <PiiTypes
            label="Tipos de dado na resposta"
            value={output.pii_types ?? []}
            onChange={(pii_types) => set({ output: { ...output, pii_types } })}
          />
        )}
        <TermsField
          id={`${id}-out`}
          label="Termos proibidos na resposta"
          hint="De 3 a 100 caracteres cada."
          value={output.blocked_terms ?? []}
          onChange={(blocked_terms) => set({ output: { ...output, blocked_terms } })}
        />
        <p className="text-[11px] text-amber-400">
          Com resposta em tempo real (modo teste, chat), o texto já foi entregue quando a regra
          roda: o run fica marcado como bloqueado. Nas integrações sem stream, a resposta é trocada
          pela mensagem de bloqueio.
        </p>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${id}-msg`} className="text-foreground text-[13px]">
          Mensagem de bloqueio
        </label>
        <input
          id={`${id}-msg`}
          value={g.blocked_message}
          maxLength={500}
          onChange={(e) => set({ blocked_message: e.target.value })}
          className={inputCls}
        />
        <span className={hintCls}>O que a pessoa vê quando uma regra barra a mensagem.</span>
      </div>
    </fieldset>
  );
}
