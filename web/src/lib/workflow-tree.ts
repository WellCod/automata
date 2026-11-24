import type { components } from "@/lib/api/schema";

type Schemas = components["schemas"];
export type StepNode = Schemas["StepNode"];
export type ParallelNode = Schemas["ParallelNode"];
export type ConditionNode = Schemas["ConditionNode"];
export type LoopNode = Schemas["LoopNode"];
export type RouterNode = Schemas["RouterNode"];
export type RouterRoute = Schemas["RouterRoute"];
export type WorkflowNode = StepNode | ParallelNode | ConditionNode | LoopNode | RouterNode;
export type WorkflowRule = Schemas["WorkflowRule"];
export type StepReview = Schemas["StepReview"];
export type NodeType = WorkflowNode["type"];

// mesmos limites de app/schemas/workflow.py: a API valida de novo na escrita
export const MAX_STEPS = 30;
export const MAX_DEPTH = 3;
export const MAX_BRANCHES = 5;
export const MAX_ROUTES = 5;

// {etapa:Nome} no texto de entrada (ADR-0038); mesma regra de STEP_REF na API
export function templateRefs(template: string | null | undefined): string[] {
  return [...(template ?? "").matchAll(/\{etapa:([^{}]{1,60})\}/g)].map((match) => match[1].trim());
}

export const RULE_KINDS: { value: WorkflowRule["kind"]; label: string; needsValue: boolean }[] = [
  { value: "contains", label: "contém", needsValue: true },
  { value: "not_contains", label: "não contém", needsValue: true },
  { value: "starts_with", label: "começa com", needsValue: true },
  { value: "empty", label: "está vazia", needsValue: false },
  { value: "not_empty", label: "não está vazia", needsValue: false },
  { value: "always", label: "sempre", needsValue: false },
];

export function ruleNeedsValue(kind: WorkflowRule["kind"]): boolean {
  return RULE_KINDS.find((option) => option.value === kind)?.needsValue ?? false;
}

// filhos diretos de um contêiner, na ordem em que aparecem no editor
export function children(node: WorkflowNode): WorkflowNode[] {
  if (node.type === "parallel") return node.branches;
  if (node.type === "condition") return [...node.steps, ...(node.else_steps ?? [])];
  if (node.type === "loop") return node.steps;
  if (node.type === "router")
    return [...node.routes.map((route) => route.step), ...(node.default ? [node.default] : [])];
  return [];
}

export function allNodes(nodes: WorkflowNode[]): WorkflowNode[] {
  return nodes.flatMap((node) => [node, ...allNodes(children(node))]);
}

export function countSteps(nodes: WorkflowNode[]): number {
  return allNodes(nodes).filter((node) => node.type === "step").length;
}

const BASE_NAME: Record<NodeType, string> = {
  step: "etapa",
  parallel: "paralelo",
  condition: "condição",
  loop: "repetição",
  router: "roteador",
};

// "etapa", "etapa 2", "etapa 3"...: o primeiro sufixo livre a partir de 2
export function uniqueName(base: string, taken: Set<string>): string {
  if (!taken.has(base)) return base;
  let suffix = 2;
  while (taken.has(`${base} ${suffix}`)) suffix += 1;
  return `${base} ${suffix}`;
}

// recebe os nomes já usados na árvore inteira: o nome é único no workflow todo
export function newNode(type: NodeType, taken: Set<string>): WorkflowNode {
  const name = uniqueName(BASE_NAME[type], taken);
  const step = (stepName: string): StepNode => ({
    type: "step",
    name: stepName,
    on_error: "stop",
    max_retries: 0,
    input: "previous",
  });
  if (type === "step") return step(name);
  // os filhos também entram no conjunto de nomes, para os dois ramos não colidirem
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
  if (type === "router") {
    const first = uniqueName("caminho", new Set([...taken, name]));
    const second = uniqueName("caminho", new Set([...taken, name, first]));
    return {
      type,
      name,
      routes: [
        { rule: { kind: "contains", source: "input", value: "" }, step: step(first) },
        { rule: { kind: "contains", source: "input", value: "" }, step: step(second) },
      ],
      default: null,
    };
  }
  const inner = uniqueName("etapa", new Set([...taken, name]));
  return { type, name, steps: [step(inner)], max_iterations: 3, until: null };
}

export function namesOf(nodes: WorkflowNode[]): Set<string> {
  return new Set(allNodes(nodes).map((node) => node.name));
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
    .flatMap((topNode) => allNodes(children(topNode)))
    .filter((node) => node.type === "step" && node.review)
    .map((node) => node.name);
}

// laço com revisão por volta (ADR-0028): no nível principal e com uma etapa simples
export function loopReviewErrors(nodes: WorkflowNode[]): string[] {
  const errors: string[] = [];
  for (const node of nodes.flatMap((topNode) => allNodes(children(topNode))))
    if (node.type === "loop" && node.review)
      errors.push(`O laço "${node.name}" com revisão precisa estar no nível principal.`);
  for (const node of nodes)
    if (
      node.type === "loop" &&
      node.review &&
      (node.steps.length !== 1 || node.steps[0].type !== "step")
    )
      errors.push(`O laço "${node.name}" com revisão por volta precisa de uma etapa só.`);
  return errors;
}

// mesmas regras estruturais da API, para avisar antes de salvar
export function structureErrors(nodes: WorkflowNode[]): string[] {
  const errors: string[] = [];
  if (nodes.length === 0) errors.push("Adicione ao menos uma etapa.");
  const all = allNodes(nodes);
  const seen = new Set<string>();
  for (const node of all) {
    if (!node.name.trim()) errors.push("Toda etapa precisa de nome.");
    else if (seen.has(node.name)) errors.push(`Nome repetido: "${node.name}".`);
    seen.add(node.name);
    if (node.type === "step" && !node.agent_id && !node.team_id)
      errors.push(`Escolha o agente ou time de "${node.name}".`);
    if ((node.type === "condition" || node.type === "loop") && node.steps.length === 0)
      errors.push(`"${node.name}" precisa de ao menos uma etapa.`);
    const rule = node.type === "condition" ? node.rule : node.type === "loop" ? node.until : null;
    if (rule && ruleNeedsValue(rule.kind) && !rule.value?.trim())
      errors.push(`Preencha o texto da regra de "${node.name}".`);
    if (node.type === "router")
      for (const route of node.routes)
        if (ruleNeedsValue(route.rule.kind) && !route.rule.value?.trim())
          errors.push(`Preencha o texto da regra do caminho "${route.step.name}".`);
    if (node.type === "step" && node.input === "template") {
      if (!node.template?.trim()) errors.push(`Escreva o texto de entrada de "${node.name}".`);
      for (const ref of templateRefs(node.template))
        if (!all.some((other) => other.name === ref))
          errors.push(`O texto de "${node.name}" cita a etapa "${ref}", que não existe.`);
    }
  }
  if (countSteps(nodes) > MAX_STEPS) errors.push(`No máximo ${MAX_STEPS} etapas.`);
  for (const name of reviewsInsideContainers(nodes))
    errors.push(`"${name}" está dentro de um contêiner: revisão humana só no nível principal.`);
  errors.push(...loopReviewErrors(nodes));
  if (nodes.at(-1)?.type === "parallel")
    errors.push("O workflow não pode terminar num paralelo: junte os ramos numa etapa.");
  return [...new Set(errors)];
}
