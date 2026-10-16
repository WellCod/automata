// Fontes citadas a partir do resultado da tool buscar_<slug> (ADR-0012), que a API
// devolve como JSON: {base, trechos: [{documento, fonte, content_id, texto}]}

export interface KnowledgeSource {
  base: string;
  documento: string;
  fonte: string | null;
}

interface ToolLike {
  tool_name?: string | null;
  result?: unknown;
}

export function isKnowledgeTool(name: string | null | undefined): boolean {
  return typeof name === "string" && name.startsWith("buscar_");
}

export function sourcesFromTool(tool: ToolLike | undefined): KnowledgeSource[] {
  if (!tool || !isKnowledgeTool(tool.tool_name) || typeof tool.result !== "string") return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(tool.result);
  } catch {
    return [];
  }
  if (!parsed || typeof parsed !== "object") return [];
  const { base, trechos } = parsed as { base?: unknown; trechos?: unknown };
  if (!Array.isArray(trechos)) return [];
  const out: KnowledgeSource[] = [];
  for (const t of trechos) {
    if (!t || typeof t !== "object") continue;
    const { documento, fonte } = t as { documento?: unknown; fonte?: unknown };
    const nome =
      typeof documento === "string" ? documento : typeof fonte === "string" ? fonte : null;
    if (!nome) continue;
    out.push({
      base: typeof base === "string" ? base : "",
      documento: nome,
      fonte: typeof fonte === "string" ? fonte : null,
    });
  }
  return out;
}

// Um documento aparece uma vez, mesmo que vários trechos dele tenham vindo
export function mergeSources(prev: KnowledgeSource[], next: KnowledgeSource[]): KnowledgeSource[] {
  const seen = new Set(prev.map((s) => `${s.base}|${s.documento}`));
  const out = [...prev];
  for (const s of next) {
    const key = `${s.base}|${s.documento}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(s);
    }
  }
  return out;
}
