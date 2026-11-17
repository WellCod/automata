import { NextRequest, NextResponse } from "next/server";

import { setSessionCookie } from "@/lib/bff/session-cookie";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// troca pela própria pessoa (ADR-0045): a API corta as outras sessões e devolve o token novo
export async function POST(req: NextRequest) {
  const token = req.cookies.get("automata_token")?.value;
  if (!token) return new NextResponse("Não autorizado", { status: 401 });

  const upstream = await fetch(`${API_URL}/api/v1/me/password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(await req.json()),
  });
  const data = (await upstream.json().catch(() => ({}))) as {
    access_token?: string;
    detail?: unknown;
  };
  if (!upstream.ok || !data.access_token) {
    return NextResponse.json({ detail: data.detail }, { status: upstream.status });
  }
  const res = NextResponse.json({ ok: true });
  setSessionCookie(res, data.access_token);
  return res;
}
