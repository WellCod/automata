// Ação da trilha (ADR-0041) em português: a API grava método e rota modelo
const LABELS: [RegExp, string][] = [
  [/^POST \/api\/v1\/configs$/, "Criou config"],
  [/^PUT \/api\/v1\/configs\/\{config_id\}\/draft$/, "Salvou rascunho"],
  [/^POST \/api\/v1\/configs\/\{config_id\}\/publish$/, "Publicou versão"],
  [/^POST \/api\/v1\/configs\/\{config_id\}\/rollback$/, "Reverteu versão"],
  [/^POST \/api\/v1\/configs\/\{config_id\}\/canary$/, "Ligou canário"],
  [/^PATCH \/api\/v1\/configs\/\{config_id\}\/canary$/, "Mudou o percentual do canário"],
  [/^POST \/api\/v1\/configs\/\{config_id\}\/canary\/promote$/, "Promoveu canário"],
  [/^DELETE \/api\/v1\/configs\/\{config_id\}\/canary$/, "Desligou canário"],
  [/^PUT \/api\/v1\/configs\/\{config_id\}\/budget$/, "Mudou orçamento"],
  [/^(POST|PUT|DELETE) \/api\/v1\/configs\/\{config_id\}\/eval-/, "Mexeu na suíte"],
  [/^PUT \/api\/v1\/instance-guardrails$/, "Mudou o piso de guardrails"],
  [/^POST \/api\/v1\/users$/, "Criou usuário"],
  [/^PATCH \/api\/v1\/users\/\{user_id\}$/, "Alterou usuário"],
  [/^POST \/api\/v1\/users\/\{user_id\}\/password$/, "Redefiniu senha"],
  [/^DELETE \/api\/v1\/users\/\{user_id\}$/, "Removeu usuário"],
  [/^POST \/api\/v1\/integrations$/, "Emitiu token de integração"],
  [/^DELETE \/api\/v1\/integrations\//, "Revogou token de integração"],
  [/\/data-subjects\/\{user_id\}\/export$/, "Exportou dados de titular"],
  [/\/data-subjects\/\{user_id\}\/erase$/, "Apagou dados de titular"],
  [/^POST \/api\/v1\/me\/data\/erase$/, "Pediu a exclusão dos próprios dados"],
  [/^PUT \/api\/v1\/caller-budgets\//, "Mudou orçamento de quem chama"],
  [/^DELETE \/api\/v1\/caller-budgets\//, "Removeu orçamento de quem chama"],
  [/^(POST|PUT|DELETE) \/api\/v1\/mcp-servers/, "Mexeu em servidor MCP"],
  [/^(POST|PUT|DELETE) \/api\/v1\/knowledge-/, "Mexeu em base de conhecimento"],
  [/^(POST|PUT|DELETE) \/api\/v1\/alert-destinations/, "Mexeu em destino de aviso"],
  [/\/runs\/\{[a-z_]+\}\/continue$/, "Decidiu aprovação"],
];

const VERBS: Record<string, string> = {
  POST: "Criou ou disparou",
  PUT: "Alterou",
  PATCH: "Alterou",
  DELETE: "Removeu",
};

export function auditLabel(action: string): string {
  for (const [pattern, label] of LABELS) if (pattern.test(action)) return label;
  const [method, path = ""] = action.split(" ");
  return `${VERBS[method] ?? method} ${path.replace(/^\/api\/v1\//, "")}`;
}

// filtro da tela: o trecho da rota que a API procura em `action`
export const ACTION_FILTERS: { value: string; label: string }[] = [
  { value: "/publish", label: "Publicação" },
  { value: "/rollback", label: "Rollback" },
  { value: "/canary", label: "Canário" },
  { value: "/instance-guardrails", label: "Piso de guardrails" },
  { value: "/users", label: "Usuários" },
  { value: "/integrations", label: "Integrações" },
  { value: "/data-subjects", label: "Titulares" },
  { value: "budget", label: "Orçamentos" },
  { value: "/continue", label: "Aprovações" },
];

type Detail = Record<string, unknown>;

function short(value: unknown): string {
  if (value === null || value === undefined) return "nada";
  if (typeof value === "boolean") return value ? "sim" : "não";
  if (typeof value === "number") return value.toLocaleString("pt-BR");
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return text.length > 60 ? `${text.slice(0, 57)}…` : text;
}

/** Frases curtas do antes e depois, com a versão pelo número. */
export function describeDetail(
  detail: Detail | null | undefined,
  versions: Record<string, number>,
): string[] {
  if (!detail) return [];
  const v = (id: unknown) =>
    typeof id === "string" && versions[id] ? `v${versions[id]}` : id ? "outra versão" : "nenhuma";
  const out: string[] = [];
  if ("current_before" in detail || "current_after" in detail)
    out.push(`vigente: ${v(detail.current_before)} → ${v(detail.current_after)}`);
  if ("canary_version" in detail) {
    const pct = typeof detail.percent === "number" ? ` em ${detail.percent}%` : "";
    out.push(`canário: ${v(detail.canary_version)}${pct}`);
  }
  if ("percent_before" in detail)
    out.push(`percentual: ${short(detail.percent_before)}% → ${short(detail.percent_after)}%`);
  const before = detail.before as Detail | null | undefined;
  const after = detail.after as Detail | null | undefined;
  if ("before" in detail || "after" in detail) {
    if (!before && after) out.push("criado");
    else if (before && !after) out.push("removido");
    else if (before && after) {
      const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
      for (const key of keys) {
        if (JSON.stringify(before[key]) !== JSON.stringify(after[key]))
          out.push(`${key}: ${short(before[key])} → ${short(after[key])}`);
      }
      if (out.length === 0) out.push("sem mudança");
    }
  }
  return out;
}
