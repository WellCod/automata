import { NextRequest, NextResponse } from "next/server";

import { API_URL, STATE_COOKIE, forwardHeaders, publicUrl } from "@/lib/bff/oidc";

function back(req: NextRequest, message: string) {
  const url = publicUrl(req, "/login");
  url.searchParams.set("sso_erro", message);
  const res = NextResponse.redirect(url);
  res.cookies.delete({ name: STATE_COOKIE, path: "/api/auth/oidc" });
  return res;
}

export async function GET(req: NextRequest) {
  const params = req.nextUrl.searchParams;
  // o provedor devolve error quando a pessoa cancela ou não tem acesso ao app
  if (params.get("error")) return back(req, "Login cancelado no provedor");
  const code = params.get("code");
  const state = params.get("state");
  const expected = req.cookies.get(STATE_COOKIE)?.value;
  if (!code || !state || !expected || state !== expected) {
    return back(req, "Login expirado; tente de novo");
  }

  let data: { access_token?: string; detail?: unknown };
  let ok = false;
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc/callback`, {
      method: "POST",
      headers: forwardHeaders(req),
      body: JSON.stringify({ code, state }),
    });
    ok = upstream.ok;
    data = (await upstream.json()) as typeof data;
  } catch {
    return back(req, "Não foi possível falar com a API");
  }
  if (!ok || !data.access_token) {
    return back(req, typeof data.detail === "string" ? data.detail : "Login recusado");
  }

  const res = NextResponse.redirect(publicUrl(req, "/"));
  res.cookies.delete({ name: STATE_COOKIE, path: "/api/auth/oidc" });
  res.cookies.set("automata_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return res;
}
