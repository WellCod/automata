import { NextRequest, NextResponse } from "next/server";

import { API_URL, BROWSER_COOKIE, type SsoError, forwardHeaders, publicUrl } from "@/lib/bff/oidc";

function back(req: NextRequest, code: SsoError) {
  const url = publicUrl(req, "/login");
  // código, não texto: a tela de login mostra só as mensagens dela (Fase 49)
  url.searchParams.set("sso_erro", code);
  const res = NextResponse.redirect(url);
  res.cookies.delete({ name: BROWSER_COOKIE, path: "/api/auth/oidc" });
  return res;
}

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  // o provedor devolve error quando a pessoa cancela ou não tem acesso ao app
  if (params.get("error")) return back(req, "cancelado");
  const code = params.get("code");
  const state = params.get("state");
  const browserKey = req.cookies.get(BROWSER_COOKIE)?.value;
  if (!code || !state || !browserKey) return back(req, "expirado");

  let data: { access_token?: string };
  let status = 0;
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc/callback`, {
      method: "POST",
      headers: forwardHeaders(req),
      body: JSON.stringify({ code, state, browser_key: browserKey }),
    });
    status = upstream.status;
    data = (await upstream.json()) as typeof data;
  } catch {
    return back(req, "indisponivel");
  }
  if (status === 403) return back(req, "sem_acesso");
  if (status === 401) return back(req, "expirado");
  if (status !== 200 || !data.access_token) return back(req, "indisponivel");

  const res = NextResponse.redirect(publicUrl(req, "/"));
  res.cookies.delete({ name: BROWSER_COOKIE, path: "/api/auth/oidc" });
  res.cookies.set("automata_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return res;
}
