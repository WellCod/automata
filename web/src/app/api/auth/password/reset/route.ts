import { NextRequest, NextResponse } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";
import { setSessionCookie } from "@/lib/bff/session-cookie";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// senha nova pelo link do e-mail; com sucesso a pessoa já entra (ADR-0045)
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as {
    token?: unknown;
    new_password?: unknown;
  };
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;

  const upstream = await fetch(`${API_URL}/api/v1/auth/password/reset`, {
    method: "POST",
    headers,
    body: JSON.stringify({ token: body.token, new_password: body.new_password }),
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
