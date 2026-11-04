"use client";

import { useQuery } from "@tanstack/react-query";
import { useId } from "react";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
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
export type CustomPiiPattern = components["schemas"]["CustomPiiPattern"];
export const MAX_CUSTOM_PATTERNS = 10;
export type ClassifierRule = components["schemas"]["ClassifierRule"];
type ClassifierCheck = ClassifierRule["checks"][number];

const CHECK_LABELS: Record<ClassifierCheck, string> = {
  injection: "Injeção de prompt, mesmo com outras palavras ou em outra língua",
  toxicity: "Ofensa, ódio, assédio ou ameaça",
  off_topic: "Assunto fora do que o agente atende",
};
export type OutputClassifierRule = components["schemas"]["OutputClassifierRule"];
type OutputCheck = OutputClassifierRule["checks"][number];
export const OUTPUT_CHECK_LABELS: Record<OutputCheck, string> = {
  toxicity: "Ofensa, ódio, assédio ou ameaça",
  off_topic: "Assunto fora do que o agente atende",
  prompt_leak: "Revela as instruções internas, o prompt ou a configuração",
};
export const DEFAULT_OUTPUT_CLASSIFIER: OutputClassifierRule = {
  model_id: "",
  checks: ["prompt_leak"],
  scope: "",
  on_failure: "allow",
};
export const DEFAULT_CLASSIFIER: ClassifierRule = {
  model_id: "",
  checks: ["injection"],
  scope: "",
  on_failure: "allow",
};

// mesmas regras de ClassifierRule e do serviço na API (ADR-0030)
export function guardrailProblems(g: Guardrails): string[] {
  const problems: string[] = [];
  const c = g.classifier;
  if (c) {
    if (!c.model_id) problems.push("Escolha o modelo do classificador.");
    if (c.checks.length === 0) problems.push("Marque ao menos uma checagem do classificador.");
    if (c.checks.includes("off_topic") && !c.scope?.trim())
      problems.push("Descreva o que o agente atende para a checagem de assunto.");
  }
  problems.push(...customPatternProblems(g.pii?.custom ?? []));
  const oc = g.output?.classifier;
  if (oc) {
    if (!oc.model_id) problems.push("Escolha o modelo do classificador da resposta.");
    if (oc.checks.length === 0)
      problems.push("Marque ao menos uma checagem do classificador da resposta.");
    if (oc.checks.includes("off_topic") && !oc.scope?.trim())
      problems.push("Descreva o que o agente atende para a checagem de assunto da resposta.");
  }
  const t = g.tool_results;
  if (t?.classifier && !c)
    problems.push("O exame de tool pelo classificador exige o classificador.");
  if (t && !t.terms && !t.classifier)
    problems.push("O exame de tool precisa de termos ou classificador.");
  return problems;
}
// mesmas regras de CustomPiiPattern na API (ADR-0032)
export function customPatternProblems(patterns: CustomPiiPattern[]): string[] {
  const problems: string[] = [];
  const labels = new Set<string>();
  patterns.forEach((p, i) => {
    const n = i + 1;
    const label = p.label.trim();
    if (!label || !/^[\p{L}\p{N}_ ]{1,30}$/u.test(label))
      problems.push(`Padrão ${n}: o rótulo precisa de 1 a 30 letras, dígitos ou espaços.`);
    else if (labels.has(label.toLowerCase())) problems.push(`Padrão ${n}: rótulo repetido.`);
    labels.add(label.toLowerCase());
    if (!/^[A-Za-z0-9-]{0,10}$/.test(p.prefix ?? ""))
      problems.push(`Padrão ${n}: o prefixo aceita até 10 letras, dígitos ou hífen.`);
    const inRange = (d: number) => Number.isInteger(d) && d >= 4 && d <= 20;
    if (!inRange(p.min_digits) || !inRange(p.max_digits))
      problems.push(`Padrão ${n}: os dígitos vão de 4 a 20.`);
    else if (p.min_digits > p.max_digits)
      problems.push(`Padrão ${n}: o mínimo de dígitos passa do máximo.`);
  });
  return problems;
}

type OutputRule = NonNullable<Guardrails["output"]>;
const DEFAULT_PII: PiiRule = { mode: "off", types: PII_TYPES, custom: [] };
const DEFAULT_OUTPUT: OutputRule = {
  pii: false,
  pii_types: PII_TYPES,
  blocked_terms: [],
  classifier: null,
};

export const DEFAULT_GUARDRAILS: Guardrails = {
  pii: DEFAULT_PII,
  prompt_injection: false,
  injection_extra_terms: [],
  blocked_topics: [],
  max_input_chars: null,
  moderation: false,
  classifier: null,
  tool_results: null,
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

function useModelIds() {
  return useQuery({
    queryKey: ["models:capabilities"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/models/capabilities");
      if (res.error) throw new Error("Falha ao carregar modelos");
      return res.data as Record<string, unknown>;
    },
    select: (models) => Object.keys(models),
  });
}

type AnyClassifier = {
  model_id: string;
  checks: string[];
  scope?: string;
  on_failure?: "allow" | "block";
};

function ClassifierFields<R extends AnyClassifier>({
  value,
  onChange,
  labels,
  subject = "mensagem",
}: {
  value: R;
  onChange: (v: R) => void;
  labels: Record<R["checks"][number], string>;
  subject?: "mensagem" | "resposta";
}) {
  const id = useId();
  const { data: models = [] } = useModelIds();
  const checks: string[] = value.checks ?? [];
  const options = Object.keys(labels) as R["checks"][number][];
  return (
    <div className="flex flex-col gap-2 pl-6">
      <label htmlFor={`${id}-model`} className="text-foreground text-[13px]">
        Modelo que classifica
      </label>
      <select
        id={`${id}-model`}
        value={value.model_id}
        onChange={(e) => onChange({ ...value, model_id: e.target.value })}
        className={inputCls}
      >
        <option value="">Escolha um modelo</option>
        {models.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
      <div
        role="group"
        aria-label={subject === "resposta" ? "Checagens da resposta" : "Checagens do classificador"}
        className="flex flex-col gap-1"
      >
        {options.map((c) => (
          <label key={c} className="text-foreground flex items-center gap-1.5 text-[13px]">
            <input
              type="checkbox"
              className={checkCls}
              checked={checks.includes(c)}
              onChange={(e) =>
                onChange({
                  ...value,
                  checks: e.target.checked ? [...checks, c] : checks.filter((x) => x !== c),
                })
              }
            />
            {labels[c]}
          </label>
        ))}
      </div>
      {checks.includes("off_topic") && (
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-scope`} className="text-foreground text-[13px]">
            O que o agente atende
          </label>
          <textarea
            id={`${id}-scope`}
            rows={2}
            maxLength={500}
            value={value.scope ?? ""}
            placeholder="ex.: pedidos, trocas e entregas da loja"
            onChange={(e) => onChange({ ...value, scope: e.target.value })}
            className={`${inputCls} resize-y`}
          />
        </div>
      )}
      <label htmlFor={`${id}-fail`} className="text-foreground text-[13px]">
        Se o classificador falhar ou passar de 10 s
      </label>
      <select
        id={`${id}-fail`}
        value={value.on_failure ?? "allow"}
        onChange={(e) => onChange({ ...value, on_failure: e.target.value as "allow" | "block" })}
        className={inputCls}
      >
        <option value="allow">Deixar a {subject} seguir</option>
        <option value="block">Bloquear a {subject}</option>
      </select>
    </div>
  );
}

function CustomPatterns({
  value,
  onChange,
}: {
  value: CustomPiiPattern[];
  onChange: (v: CustomPiiPattern[]) => void;
}) {
  const id = useId();
  const update = (i: number, patch: Partial<CustomPiiPattern>) =>
    onChange(value.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-foreground text-[13px]">Padrões próprios</span>
      <span className={hintCls}>
        Matrícula, contrato ou protocolo da empresa, pelo prefixo e pela quantidade de dígitos
        (pontos, hífens e espaços entre eles são aceitos). Valem na entrada quando a verificação
        está ligada, na memória do usuário e na resposta. Sem prefixo, qualquer número com essa
        quantidade de dígitos é mascarado.
      </span>
      {value.map((p, i) => (
        <div
          key={i}
          role="group"
          aria-label={`Padrão ${i + 1}`}
          className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1fr_8rem_5rem_5rem_auto]"
        >
          <label className="flex flex-col gap-1 text-[11px]">
            <span className="text-muted-foreground">Rótulo</span>
            <input
              id={`${id}-label-${i}`}
              className={inputCls}
              value={p.label}
              maxLength={30}
              placeholder="matrícula"
              onChange={(e) => update(i, { label: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px]">
            <span className="text-muted-foreground">Prefixo</span>
            <input
              className={inputCls}
              value={p.prefix ?? ""}
              maxLength={10}
              placeholder="MAT"
              onChange={(e) => update(i, { prefix: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px]">
            <span className="text-muted-foreground">Mín. dígitos</span>
            <input
              type="number"
              min={4}
              max={20}
              className={inputCls}
              value={p.min_digits}
              onChange={(e) => update(i, { min_digits: Number(e.target.value) })}
            />
          </label>
          <label className="flex flex-col gap-1 text-[11px]">
            <span className="text-muted-foreground">Máx. dígitos</span>
            <input
              type="number"
              min={4}
              max={20}
              className={inputCls}
              value={p.max_digits}
              onChange={(e) => update(i, { max_digits: Number(e.target.value) })}
            />
          </label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={`Remover o padrão ${i + 1}`}
            onClick={() => onChange(value.filter((_, j) => j !== i))}
          >
            Remover
          </Button>
        </div>
      ))}
      {value.length < MAX_CUSTOM_PATTERNS && (
        <Button
          type="button"
          variant="muted"
          size="sm"
          className="self-start"
          onClick={() =>
            onChange([...value, { label: "", prefix: "", min_digits: 6, max_digits: 10 }])
          }
        >
          Adicionar padrão
        </Button>
      )}
    </div>
  );
}

/** O que o piso da instância (ADR-0034) impõe, em frases curtas para o editor do agente. */
export function floorSummary(f: Guardrails | null | undefined): string[] {
  if (!f) return [];
  const g = withDefaults(f);
  const items: string[] = [];
  if (g.pii?.mode && g.pii.mode !== "off") {
    const types = (g.pii.types ?? []).map((t) => PII_LABELS[t]).join(", ");
    items.push(
      `${g.pii.mode === "block" ? "Bloquear" : "Mascarar"} dados pessoais${types ? ` (${types})` : ""}`,
    );
  }
  if (g.pii?.custom?.length)
    items.push(`Padrões próprios: ${g.pii.custom.map((c) => c.label).join(", ")}`);
  if (g.prompt_injection) items.push("Bloquear injeção de prompt");
  if (g.blocked_topics?.length) items.push(`Tópicos proibidos: ${g.blocked_topics.join(", ")}`);
  if (g.max_input_chars)
    items.push(`Mensagem de até ${g.max_input_chars.toLocaleString("pt-BR")} caracteres`);
  if (g.moderation) items.push("Moderação da OpenAI");
  if (g.classifier) items.push(`Classificador da entrada (${g.classifier.model_id})`);
  if (g.tool_results) items.push("Exame do resultado de tool");
  if (g.output?.pii) items.push("Barrar dado pessoal na resposta");
  if (g.output?.blocked_terms?.length) items.push("Termos proibidos na resposta");
  if (g.output?.classifier)
    items.push(`Classificador da resposta (${g.output.classifier.model_id})`);
  return items;
}

export function GuardrailsEditor({
  value,
  onChange,
  floor,
  instance = false,
}: {
  value: Guardrails;
  onChange: (v: Guardrails) => void;
  /** piso da instância que este agente herda; o editor só mostra */
  floor?: Guardrails | null;
  /** editando o próprio piso: muda o texto de quando passa a valer */
  instance?: boolean;
}) {
  const inherited = floorSummary(floor);
  const id = useId();
  const g = withDefaults(value);
  const pii = g.pii!;
  const output = g.output!;
  const set = (patch: Partial<Guardrails>) => onChange({ ...g, ...patch });
  const problems = guardrailProblems(g);

  return (
    <fieldset className="border-border flex flex-col gap-4 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">Guardrails</legend>
      <p className={hintCls}>
        {instance
          ? "Mínimo que todo agente e time segue. O agente só pode endurecer estas regras, e a mudança vale no próximo run, sem publicar os agentes de novo. A mensagem de bloqueio é sempre a do agente."
          : "Regras checadas antes de a mensagem chegar ao modelo: bloquear não gasta token. Valem a partir da próxima publicação, como as instruções."}
      </p>
      {inherited.length > 0 && (
        <div
          role="note"
          aria-label="Piso da instância"
          className="border-accent/40 bg-accent/5 flex flex-col gap-1 rounded border px-3 py-2"
        >
          <span className="text-foreground text-[12px] font-medium">
            O piso da instância já vale para este agente, mesmo com as opções abaixo desligadas:
          </span>
          <ul className="text-muted-foreground list-disc pl-5 text-[12px]">
            {inherited.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

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

      <CustomPatterns
        value={pii.custom ?? []}
        onChange={(custom) => set({ pii: { ...pii, custom } })}
      />

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

      <label className="text-foreground flex items-start gap-2 text-[13px]">
        <input
          type="checkbox"
          className={`${checkCls} mt-0.5`}
          checked={g.classifier != null}
          onChange={(e) =>
            set({
              classifier: e.target.checked ? { ...DEFAULT_CLASSIFIER } : null,
              // sem classificador, o exame de tool fica só com os termos
              tool_results:
                e.target.checked || !g.tool_results
                  ? g.tool_results
                  : { ...g.tool_results, classifier: false, terms: true },
            })
          }
        />
        <span className="flex flex-col gap-0.5">
          Classificador por modelo
          <span className={hintCls}>
            Um modelo julga a mensagem antes do run e pega o que a lista de termos não pega. É uma
            chamada a mais por mensagem, com o custo no agente.
          </span>
        </span>
      </label>
      {g.classifier && (
        <ClassifierFields
          value={g.classifier}
          labels={CHECK_LABELS}
          onChange={(classifier) => set({ classifier })}
        />
      )}

      <div className="border-border flex flex-col gap-2 border-t pt-3">
        <span className="text-foreground text-[13px] font-medium">Resultado das tools</span>
        <label className="text-foreground flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            className={checkCls}
            checked={g.tool_results != null}
            onChange={(e) =>
              set({ tool_results: e.target.checked ? { terms: true, classifier: false } : null })
            }
          />
          Examinar o que as tools devolvem antes de o modelo ler
        </label>
        {g.tool_results && (
          <div className="flex flex-col gap-1 pl-6">
            <label className="text-foreground flex items-center gap-1.5 text-[13px]">
              <input
                type="checkbox"
                className={checkCls}
                checked={g.tool_results.terms ?? true}
                onChange={(e) =>
                  set({ tool_results: { ...g.tool_results!, terms: e.target.checked } })
                }
              />
              Pelos termos de injeção e de instrução dirigida ao assistente
            </label>
            <label className="text-foreground flex items-center gap-1.5 text-[13px]">
              <input
                type="checkbox"
                className={checkCls}
                disabled={!g.classifier}
                checked={g.tool_results.classifier ?? false}
                onChange={(e) =>
                  set({ tool_results: { ...g.tool_results!, classifier: e.target.checked } })
                }
              />
              Também pelo classificador{" "}
              {g.classifier ? "(uma chamada por tool)" : "(ligue o classificador)"}
            </label>
          </div>
        )}
        <span className={hintCls}>
          Vale para tools MCP e para a busca nas bases. Um resultado com instrução embutida (“nota
          para a IA: envie os dados…”) chega ao modelo como aviso, e o run segue com a retirada
          registrada.
        </span>
      </div>

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
        <label className="text-foreground flex items-center gap-2 text-[13px]">
          <input
            type="checkbox"
            className={checkCls}
            checked={output.classifier != null}
            onChange={(e) =>
              set({
                output: {
                  ...output,
                  classifier: e.target.checked ? { ...DEFAULT_OUTPUT_CLASSIFIER } : null,
                },
              })
            }
          />
          Julgar a resposta com um classificador por modelo
        </label>
        {output.classifier && (
          <ClassifierFields
            value={output.classifier}
            labels={OUTPUT_CHECK_LABELS}
            subject="resposta"
            onChange={(classifier) => set({ output: { ...output, classifier } })}
          />
        )}
        {output.classifier && (
          <span className={hintCls}>
            Uma chamada de modelo a mais por resposta, que entra no consumo do agente.
          </span>
        )}
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
      {problems.length > 0 && (
        <ul role="alert" className="text-destructive list-disc pl-5 text-[12px]">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
    </fieldset>
  );
}
