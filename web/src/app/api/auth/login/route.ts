import { NextRequest, NextResponse } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";
import { setSessionCookie } from "@/lib/bff/session-cookie";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const body = await req.json();

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Sem isso todo login chega à API com o IP do BFF e o rate limit vira global
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;

  const upstream = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });

  const data = (await upstream.json()) as {
    access_token?: string;
    must_change_password?: boolean;
  };

  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status });
  }

  // senha provisória do owner: o painel manda para a troca (ADR-0045)
  const res = NextResponse.json({ ok: true, must_change_password: !!data.must_change_password });
  setSessionCookie(res, data.access_token!);
  return res;
}
