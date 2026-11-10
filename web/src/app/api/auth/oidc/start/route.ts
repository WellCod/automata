import { NextRequest, NextResponse } from "next/server";

import { API_URL, STATE_COOKIE, forwardHeaders, publicUrl, safeRedirect } from "@/lib/bff/oidc";

function back(req: NextRequest, message: string) {
  const url = publicUrl(req, "/login");
  url.searchParams.set("sso_erro", message);
  return NextResponse.redirect(url);
}

export async function GET(req: NextRequest) {
  let data: { url?: unknown; detail?: unknown };
  let ok = false;
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc/start`, {
      method: "POST",
      headers: forwardHeaders(req),
    });
    ok = upstream.ok;
    data = (await upstream.json()) as typeof data;
  } catch {
    return back(req, "Não foi possível falar com a API");
  }
  const target = ok ? safeRedirect(data.url) : null;
  if (!target) {
    return back(req, typeof data.detail === "string" ? data.detail : "SSO indisponível");
  }
  const state = new URL(target).searchParams.get("state") ?? "";
  const res = NextResponse.redirect(target);
  res.cookies.set(STATE_COOKIE, state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    // lax: o provedor volta por navegação de topo (GET), e o cookie vai junto
    sameSite: "lax",
    path: "/api/auth/oidc",
    maxAge: 10 * 60,
  });
  return res;
}
