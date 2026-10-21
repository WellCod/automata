import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type TextCheck = Schemas["TextCheck"];
export type ToolsCheck = Schemas["ToolsCheck"];
export type JudgeCheck = Schemas["JudgeCheck"];
export type EvalCheck = TextCheck | ToolsCheck | JudgeCheck;
export type EvalCase = Schemas["EvalCaseResponse"];
export type EvalCaseInput = Schemas["EvalCaseInput"];
export type EvalRunSummary = Schemas["EvalRunSummary"];
export type EvalRunDetail = Schemas["EvalRunDetail"];
export type EvalResult = Schemas["EvalResultResponse"];
export type EvalSettings = Schemas["EvalSettings"];
export type EvalComparison = Schemas["EvalComparison"];

// mesmos limites de app/schemas/eval.py: a API valida de novo na escrita
export const MAX_CHECKS = 5;

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
};

export function newCheck(type: EvalCheck["type"]): EvalCheck {
  if (type === "text") return { type, kind: "contains", value: "" };
  if (type === "tools") return { type, tools: [], allow_additional: true };
  return { type, criteria: "", mode: "binary", threshold: 7 };
}

export function textNeedsValue(kind: TextCheck["kind"]): boolean {
  return TEXT_KINDS.find((k) => k.value === kind)?.needsValue ?? false;
}

// tipos que ainda cabem: o Case do Agno tem um campo de tools e um de critério
export function availableTypes(checks: EvalCheck[]): EvalCheck["type"][] {
  if (checks.length >= MAX_CHECKS) return [];
  return (["text", "tools", "judge"] as const).filter(
    (t) => t === "text" || !checks.some((c) => c.type === t),
  );
}

export function caseErrors(input: EvalCaseInput): string[] {
  const errors: string[] = [];
  if (!input.name.trim()) errors.push("Dê um nome ao caso.");
  if (!input.input.trim()) errors.push("Escreva a mensagem de entrada.");
  if (input.checks.length === 0) errors.push("Adicione ao menos uma checagem.");
  for (const c of input.checks) {
    if (c.type === "text" && textNeedsValue(c.kind) && !c.value?.trim())
      errors.push("Preencha o texto da regra.");
    if (c.type === "tools" && c.tools.length === 0) errors.push("Liste ao menos uma tool.");
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
