import { NextRequest, NextResponse } from "next/server";

import { API_URL, BROWSER_COOKIE, type SsoError, forwardHeaders, publicUrl } from "@/lib/bff/oidc";

// volta ao login com o motivo e apaga o segredo do navegador, que só vale para uma tentativa
function backToLogin(req: NextRequest, code: SsoError) {
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
  if (params.get("error")) return backToLogin(req, "cancelado");
  const code = params.get("code");
  const state = params.get("state");
  const browserKey = req.cookies.get(BROWSER_COOKIE)?.value;
  if (!code || !state || !browserKey) return backToLogin(req, "expirado");

  let callbackBody: { access_token?: string };
  let status = 0;
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc/callback`, {
      method: "POST",
      headers: forwardHeaders(req),
      body: JSON.stringify({ code, state, browser_key: browserKey }),
    });
    status = upstream.status;
    callbackBody = (await upstream.json()) as typeof callbackBody;
  } catch {
    return backToLogin(req, "indisponivel");
  }
  if (status === 403) return backToLogin(req, "sem_acesso");
  if (status === 401) return backToLogin(req, "expirado");
  if (status !== 200 || !callbackBody.access_token) return backToLogin(req, "indisponivel");

  const response = NextResponse.redirect(publicUrl(req, "/"));
  response.cookies.delete({ name: BROWSER_COOKIE, path: "/api/auth/oidc" });
  response.cookies.set("automata_token", callbackBody.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return response;
}
