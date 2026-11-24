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

  const loginBody = (await upstream.json()) as {
    access_token?: string;
    must_change_password?: boolean;
  };

  if (!upstream.ok) {
    return NextResponse.json(loginBody, { status: upstream.status });
  }

  // senha provisória do owner: o painel manda para a troca (ADR-0045)
  const response = NextResponse.json({
    ok: true,
    must_change_password: !!loginBody.must_change_password,
  });
  setSessionCookie(response, loginBody.access_token!);
  return response;
}
