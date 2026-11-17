import { NextRequest, NextResponse } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// pede o link de recuperação; a API responde 202 exista ou não a conta (ADR-0045)
export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as { email?: unknown };
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;

  const upstream = await fetch(`${API_URL}/api/v1/auth/password/forgot`, {
    method: "POST",
    headers,
    body: JSON.stringify({ email: body.email }),
  });
  if (upstream.status === 202) return NextResponse.json({ ok: true }, { status: 202 });
  return NextResponse.json({ ok: false }, { status: upstream.status });
}
