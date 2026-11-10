import type { NextRequest } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";

export const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// prende o login ao navegador que começou: sem isso, um link com o code e o state de
// outra pessoa logaria a vítima na conta dela (login CSRF)
export const STATE_COOKIE = "automata_oidc_state";

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
// redirect precisa do endereço que o navegador usou
export function publicUrl(req: NextRequest, path: string): URL {
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  const proto =
    req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim() ??
    req.nextUrl.protocol.replace(":", "");
  return host ? new URL(path, `${proto}://${host}`) : new URL(path, req.url);
}
