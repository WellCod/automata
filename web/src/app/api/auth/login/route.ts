import { NextRequest, NextResponse } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";

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

  const data = (await upstream.json()) as { access_token?: string };

  if (!upstream.ok) {
    return NextResponse.json(data, { status: upstream.status });
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.set("automata_token", data.access_token!, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
  return res;
}
