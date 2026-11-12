import { randomBytes } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

import {
  API_URL,
  BROWSER_COOKIE,
  type SsoError,
  forwardHeaders,
  publicUrl,
  safeRedirect,
} from "@/lib/bff/oidc";

function back(req: NextRequest, code: SsoError) {
  const url = publicUrl(req, "/login");
  url.searchParams.set("sso_erro", code);
  return NextResponse.redirect(url);
}

export async function GET(req: NextRequest) {
  // segredo que só este navegador tem: o state vai na URL e sozinho não prende o login
  // a ninguém; a API guarda o hash e exige o segredo de volta no retorno (Fase 49)
  const browserKey = randomBytes(32).toString("base64url");
  let data: { url?: unknown };
  let ok = false;
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc/start`, {
      method: "POST",
      headers: forwardHeaders(req),
      body: JSON.stringify({ browser_key: browserKey }),
    });
    ok = upstream.ok;
    data = (await upstream.json()) as typeof data;
  } catch {
    return back(req, "indisponivel");
  }
  const target = ok ? safeRedirect(data.url) : null;
  if (!target) return back(req, "indisponivel");
  const res = NextResponse.redirect(target);
  res.cookies.set(BROWSER_COOKIE, browserKey, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    // lax: o provedor volta por navegação de topo (GET), e o cookie vai junto
    sameSite: "lax",
    path: "/api/auth/oidc",
    maxAge: 10 * 60,
  });
  return res;
}
