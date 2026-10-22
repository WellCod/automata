import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type TextCheck = Schemas["TextCheck"];
export type ToolsCheck = Schemas["ToolsCheck"];
export type JudgeCheck = Schemas["JudgeCheck"];
export type BlockedCheck = Schemas["BlockedCheck"];
export type StepsCheck = Schemas["StepsCheck"];
export type EvalCheck = TextCheck | ToolsCheck | JudgeCheck | BlockedCheck | StepsCheck;
export type SuiteKind = "agent" | "team" | "workflow";
export type BlockRule = NonNullable<BlockedCheck["rule"]>;
export type EvalCase = Schemas["EvalCaseResponse"];
export type EvalCaseInput = Schemas["EvalCaseInput"];
export type EvalRunSummary = Schemas["EvalRunSummary"];
export type EvalRunDetail = Schemas["EvalRunDetail"];
export type EvalResult = Schemas["EvalResultResponse"];
export type EvalSettings = Schemas["EvalSettings"];
export type EvalComparison = Schemas["EvalComparison"];

// mesmos limites de app/schemas/eval.py: a API valida de novo na escrita
export const MAX_CHECKS = 5;
export const MAX_CONTEXT = 5;

export const TEXT_KINDS: { value: TextCheck["kind"]; label: string; needsValue: boolean }[] = [
  { value: "contains", label: "contém", needsValue: true },
  { value: "not_contains", label: "não contém", needsValue: true },
  { value: "starts_with", label: "começa com", needsValue: true },
  { value: "empty", label: "está vazia", needsValue: false },
  { value: "not_empty", label: "não está vazia", needsValue: false },
];

export const CHECK_LABEL: Record<EvalCheck["type"], string> = {
  text: "Texto da resposta",
  tools: "Tools chamadas",
  judge: "Critério do juiz",
  blocked: "Bloqueio do guardrail",
  steps: "Etapas que rodaram",
};

// mesmo recorte de CHECKS_BY_KIND em app/schemas/eval.py: tools e bloqueio são de
// cada etapa do workflow, e etapas só existem nele (ADR-0022)
const TYPES_BY_KIND: Record<SuiteKind, EvalCheck["type"][]> = {
  agent: ["text", "tools", "judge", "blocked"],
  team: ["text", "tools", "judge", "blocked"],
  workflow: ["text", "judge", "steps"],
};

// regras que um caso pode esperar (ADR-0022); orçamento não entra, não é comportamento
export const BLOCK_RULES: BlockRule[] = [
  "pii_detected",
  "prompt_injection",
  "off_topic",
  "input_too_long",
  "moderation",
  "output_not_allowed",
];

export function newCheck(type: EvalCheck["type"]): EvalCheck {
  if (type === "text") return { type, kind: "contains", value: "" };
  if (type === "tools") return { type, tools: [], allow_additional: true };
  if (type === "blocked") return { type, rule: null };
  if (type === "steps") return { type, steps: [], exclusive: false };
  return { type, criteria: "", mode: "binary", threshold: 7 };
}

export function textNeedsValue(kind: TextCheck["kind"]): boolean {
  return TEXT_KINDS.find((k) => k.value === kind)?.needsValue ?? false;
}

// tipos que ainda cabem: o Case do Agno tem um campo de tools e um de critério, e o
// caso que espera bloqueio não leva outra checagem (run barrado não tem resposta)
export function availableTypes(
  checks: EvalCheck[],
  kind: SuiteKind = "agent",
): EvalCheck["type"][] {
  if (checks.length >= MAX_CHECKS || checks.some((c) => c.type === "blocked")) return [];
  return TYPES_BY_KIND[kind].filter((t) => {
    if (t === "blocked") return checks.length === 0;
    return t === "text" || !checks.some((c) => c.type === t);
  });
}

export function caseErrors(input: EvalCaseInput): string[] {
  const errors: string[] = [];
  if (!input.name.trim()) errors.push("Dê um nome ao caso.");
  if (!input.input.trim()) errors.push("Escreva a mensagem de entrada.");
  if ((input.context ?? []).some((m) => !m.trim()))
    errors.push("Preencha ou remova a mensagem anterior vazia.");
  if (input.checks.length === 0) errors.push("Adicione ao menos uma checagem.");
  if (input.checks.length > 1 && input.checks.some((c) => c.type === "blocked"))
    errors.push("Caso que espera bloqueio não leva outras checagens.");
  for (const c of input.checks) {
    if (c.type === "text" && textNeedsValue(c.kind) && !c.value?.trim())
      errors.push("Preencha o texto da regra.");
    if (c.type === "tools" && c.tools.length === 0) errors.push("Liste ao menos uma tool.");
    if (c.type === "steps" && c.steps.length === 0) errors.push("Liste ao menos uma etapa.");
    if (c.type === "judge" && c.criteria.trim().length < 10)
      errors.push("O critério do juiz precisa de ao menos 10 caracteres.");
  }
  return [...new Set(errors)];
}

export function hasJudge(cases: EvalCase[]): boolean {
  return cases.some((c) => c.checks.some((check) => check.type === "judge"));
}

export const RESULT_LABEL: Record<EvalResult["status"], string> = {
  passed: "passou",
  failed: "falhou",
  error: "erro",
  not_evaluated: "não avaliado",
};

export const CHANGE_LABEL: Record<EvalComparison["cases"][number]["change"], string> = {
  regression: "regressão",
  fix: "corrigido",
  same: "igual",
  new: "novo",
  removed: "removido",
};

export function runActive(run: Pick<EvalRunSummary, "status"> | undefined): boolean {
  return run?.status === "queued" || run?.status === "running";
}

export type EvalSchedule = Schemas["EvalScheduleResponse"];
export type EvalScheduleInput = Schemas["EvalScheduleInput"];
export type EvalSuiteStatus = Schemas["EvalSuiteStatus"];

export const TRIGGER_LABEL: Record<EvalRunSummary["trigger"], string> = {
  manual: "manual",
  integration: "integração",
  schedule: "agendada",
};

export const SUITE_STATE_LABEL: Record<EvalSuiteStatus["state"], string> = {
  running: "Suíte rodando",
  passing: "Suíte verde",
  failing: "Suíte falhando",
  regressed: "Suíte regrediu",
};

// frequências prontas; o cron livre fica como avançado. Intervalo mínimo da API: 1 hora
export const SCHEDULE_PRESETS: { label: string; cron: string }[] = [
  { label: "A cada 6 horas", cron: "0 */6 * * *" },
  { label: "Todo dia às 8h", cron: "0 8 * * *" },
  { label: "Dias úteis às 8h", cron: "0 8 * * 1-5" },
  { label: "Toda segunda às 8h", cron: "0 8 * * 1" },
];

export type EvalCaseSuggestion = Schemas["EvalCaseSuggestion"];
