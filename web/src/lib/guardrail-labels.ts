// Motivos de bloqueio gravados em agent_run.blocked_by (ADR-0013)
export const BLOCK_LABELS: Record<string, string> = {
  pii_detected: "Dados pessoais",
  prompt_injection: "Injeção de prompt",
  off_topic: "Tópico proibido",
  input_too_long: "Mensagem longa demais",
  moderation: "Moderação",
  classifier: "Classificador",
  output_not_allowed: "Resposta barrada",
  // orçamento do mês estourado com bloqueio ligado (ADR-0021)
  budget_exceeded: "Orçamento do mês",
};

export function blockLabel(rule: string | null | undefined): string {
  if (!rule) return "Guardrail";
  return BLOCK_LABELS[rule] ?? rule;
}

export const CHECK_ERROR_TYPES = new Set(["input_check_error", "output_check_error"]);

// guardrail funcionando não é falha: aparece à parte, com os motivos mais comuns
export function blockedHint(byRule: Record<string, number>): string {
  const top = Object.entries(byRule)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([rule, n]) => `${blockLabel(rule)} ${n}`);
  return top.length ? top.join(" · ") : "mensagens barradas por guardrail";
}

// resultados de tool retirados por instrução embutida (ADR-0030); o trecho fica só no banco
export function screenedText(items: { tool: string }[]): string {
  const tools = [...new Set(items.map((i) => i.tool))].join(", ");
  const n = items.length;
  return `${n} resultado${n === 1 ? "" : "s"} de tool retirado${n === 1 ? "" : "s"} por instrução embutida: ${tools}`;
}

// run encerrado antes do fim sem ser erro (ADR-0031)
export const STOP_LABELS: Record<string, string> = {
  run_cost_limit: "Parado pelo teto de custo",
};

export function stopLabel(reason: string): string {
  return STOP_LABELS[reason] ?? reason;
}
