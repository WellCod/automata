import { NextResponse } from "next/server";

import { API_URL } from "@/lib/bff/oidc";

// tela de login: se o SSO está ligado e o texto do botão
export async function GET() {
  try {
    const upstream = await fetch(`${API_URL}/api/v1/auth/oidc`, { cache: "no-store" });
    if (!upstream.ok) return NextResponse.json({ enabled: false, label: "", password_login: true });
    return NextResponse.json(await upstream.json());
  } catch {
    return NextResponse.json({ enabled: false, label: "", password_login: true });
  }
}
