import { NextRequest, NextResponse } from "next/server";

import { clientIp } from "@/lib/bff/client-ip";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// a API confere a assinatura sobre estes bytes: o corpo segue cru, sem parse
const FORWARDED = [
  "content-type",
  "x-hub-signature-256",
  "x-slack-signature",
  "x-slack-request-timestamp",
  "x-slack-retry-num",
];

// webhook dos canais (ADR-0044): o WhatsApp e o Slack chamam o painel, que é o único
// endereço público; a API fica na rede interna. Sem cookie, a assinatura é a proteção
async function forward(req: NextRequest, id: string, method: "GET" | "POST") {
  if (!UUID.test(id)) return NextResponse.json({ detail: "Not Found" }, { status: 404 });
  const headers: Record<string, string> = {};
  for (const name of FORWARDED) {
    const value = req.headers.get(name);
    if (value) headers[name] = value;
  }
  const ip = clientIp(req);
  if (ip) headers["X-Forwarded-For"] = ip;
  const query = method === "GET" ? req.nextUrl.search : "";
  const upstream = await fetch(`${API_URL}/hooks/channels/${id}${query}`, {
    method,
    headers,
    body: method === "POST" ? await req.arrayBuffer() : undefined,
  });
  return new NextResponse(await upstream.arrayBuffer(), {
    status: upstream.status,
    headers: { "Content-Type": upstream.headers.get("content-type") ?? "text/plain" },
  });
}

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return forward(req, (await ctx.params).id, "GET");
}

export async function POST(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  return forward(req, (await ctx.params).id, "POST");
}
