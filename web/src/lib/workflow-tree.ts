import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type StepNode = Schemas["StepNode"];
export type ParallelNode = Schemas["ParallelNode"];
export type ConditionNode = Schemas["ConditionNode"];
export type LoopNode = Schemas["LoopNode"];
export type WorkflowNode = StepNode | ParallelNode | ConditionNode | LoopNode;
export type WorkflowRule = Schemas["WorkflowRule"];
export type StepReview = Schemas["StepReview"];
export type NodeType = WorkflowNode["type"];

// mesmos limites de app/schemas/workflow.py: a API valida de novo na escrita
export const MAX_STEPS = 30;
export const MAX_DEPTH = 3;
export const MAX_BRANCHES = 5;

export const RULE_KINDS: { value: WorkflowRule["kind"]; label: string; needsValue: boolean }[] = [
  { value: "contains", label: "contém", needsValue: true },
  { value: "not_contains", label: "não contém", needsValue: true },
  { value: "starts_with", label: "começa com", needsValue: true },
  { value: "empty", label: "está vazia", needsValue: false },
  { value: "not_empty", label: "não está vazia", needsValue: false },
  { value: "always", label: "sempre", needsValue: false },
];

export function ruleNeedsValue(kind: WorkflowRule["kind"]): boolean {
  return RULE_KINDS.find((k) => k.value === kind)?.needsValue ?? false;
}

export function children(node: WorkflowNode): WorkflowNode[] {
  if (node.type === "parallel") return node.branches;
  if (node.type === "condition") return [...node.steps, ...(node.else_steps ?? [])];
  if (node.type === "loop") return node.steps;
  return [];
}

export function allNodes(nodes: WorkflowNode[]): WorkflowNode[] {
  return nodes.flatMap((n) => [n, ...allNodes(children(n))]);
}

export function countSteps(nodes: WorkflowNode[]): number {
  return allNodes(nodes).filter((n) => n.type === "step").length;
}

const BASE_NAME: Record<NodeType, string> = {
  step: "etapa",
  parallel: "paralelo",
  condition: "condição",
  loop: "repetição",
};

export function uniqueName(base: string, taken: Set<string>): string {
  if (!taken.has(base)) return base;
  let i = 2;
  while (taken.has(`${base} ${i}`)) i += 1;
  return `${base} ${i}`;
}

// recebe os nomes já usados na árvore inteira: o nome é único no workflow todo
export function newNode(type: NodeType, taken: Set<string>): WorkflowNode {
  const name = uniqueName(BASE_NAME[type], taken);
  const step = (n: string): StepNode => ({
    type: "step",
    name: n,
    on_error: "stop",
    max_retries: 0,
  });
  if (type === "step") return step(name);
  if (type === "parallel") {
    const first = uniqueName("ramo", new Set([...taken, name]));
    const second = uniqueName("ramo", new Set([...taken, name, first]));
    return { type, name, branches: [step(first), step(second)] };
  }
  if (type === "condition") {
    const inner = uniqueName("etapa", new Set([...taken, name]));
    return {
      type,
      name,
      rule: { kind: "contains", source: "input", value: "" },
      steps: [step(inner)],
      else_steps: [],
    };
  }
  const inner = uniqueName("etapa", new Set([...taken, name]));
  return { type, name, steps: [step(inner)], max_iterations: 3, until: null };
}

export function namesOf(nodes: WorkflowNode[]): Set<string> {
  return new Set(allNodes(nodes).map((n) => n.name));
}

export function move<T>(list: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (target < 0 || target >= list.length) return list;
  const next = [...list];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function replaceAt<T>(list: T[], index: number, item: T): T[] {
  return list.map((current, i) => (i === index ? item : current));
}

export function removeAt<T>(list: T[], index: number): T[] {
  return list.filter((_, i) => i !== index);
}

// revisão humana só no nível principal (ADR-0023): o Agno 3.1.8 não pausa etapa
// dentro de condição, e em paralelo e laço o contêiner ficaria pela metade
export function reviewsInsideContainers(nodes: WorkflowNode[]): string[] {
  return nodes
    .flatMap((n) => allNodes(children(n)))
    .filter((n) => n.type === "step" && n.review)
    .map((n) => n.name);
}

// mesmas regras estruturais da API, para avisar antes de salvar
export function structureErrors(nodes: WorkflowNode[]): string[] {
  const errors: string[] = [];
  if (nodes.length === 0) errors.push("Adicione ao menos uma etapa.");
  const all = allNodes(nodes);
  const seen = new Set<string>();
  for (const n of all) {
    if (!n.name.trim()) errors.push("Toda etapa precisa de nome.");
    else if (seen.has(n.name)) errors.push(`Nome repetido: "${n.name}".`);
    seen.add(n.name);
    if (n.type === "step" && !n.agent_id && !n.team_id)
      errors.push(`Escolha o agente ou time de "${n.name}".`);
    if ((n.type === "condition" || n.type === "loop") && n.steps.length === 0)
      errors.push(`"${n.name}" precisa de ao menos uma etapa.`);
    const rule = n.type === "condition" ? n.rule : n.type === "loop" ? n.until : null;
    if (rule && ruleNeedsValue(rule.kind) && !rule.value?.trim())
      errors.push(`Preencha o texto da regra de "${n.name}".`);
  }
  if (countSteps(nodes) > MAX_STEPS) errors.push(`No máximo ${MAX_STEPS} etapas.`);
  for (const name of reviewsInsideContainers(nodes))
    errors.push(`"${name}" está dentro de um contêiner: revisão humana só no nível principal.`);
  if (nodes.at(-1)?.type === "parallel")
    errors.push("O workflow não pode terminar num paralelo: junte os ramos numa etapa.");
  return [...new Set(errors)];
}
