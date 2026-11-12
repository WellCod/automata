import type { NextRequest } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";

export const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// segredo do navegador que começou o login (Fase 49): sem ele, code e state vazados
// não viram sessão, e um link com o login de outra pessoa não loga a vítima (login CSRF)
export const BROWSER_COOKIE = "automata_oidc_browser";

// o que a tela de login sabe explicar; texto livre na URL vira mensagem no domínio oficial
export type SsoError = "cancelado" | "expirado" | "sem_acesso" | "indisponivel";

export function forwardHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;
  return headers;
}

// a URL do provedor vem da API, mas o painel só redireciona para https
export function safeRedirect(url: unknown): string | null {
  if (typeof url !== "string") return null;
  try {
    return new URL(url).protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

// no standalone, req.url traz o endereço em que o Next escuta (0.0.0.0:3000); o
// redirect precisa do endereço que o navegador usou. Com PUBLIC_URL, nenhum cabeçalho
// da requisição decide o destino
export function publicUrl(req: NextRequest, path: string): URL {
  const configured = process.env.PUBLIC_URL?.trim();
  if (configured) return new URL(path, configured);
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const proto =
    req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ??
    req.nextUrl.protocol.replace(":", "");
  return host ? new URL(path, `${proto}://${host}`) : new URL(path, req.url);
}
