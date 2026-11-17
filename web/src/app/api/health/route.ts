import { NextResponse } from "next/server";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// Monitor externo (OPS-05): a API não tem porta publicada, então o estado dela sai por aqui,
// sem sessão, junto com a versão do painel
export async function GET() {
  const panel = {
    version: process.env.AUTOMATA_VERSION ?? "dev",
    revision: process.env.AUTOMATA_REVISION ?? "",
  };
  try {
    const upstream = await fetch(`${API_URL}/health`, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    const api = (await upstream.json()) as Record<string, unknown>;
    return NextResponse.json(
      { status: api.status ?? "degraded", api, panel },
      { status: upstream.status, headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return NextResponse.json(
      { status: "degraded", api: { status: "unreachable" }, panel },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
