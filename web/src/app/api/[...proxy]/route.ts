import { decodeJwt } from "jose";
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

function expiredResponse(): NextResponse {
  const res = new NextResponse("Sessão expirada", { status: 401 });
  res.cookies.delete("automata_token");
  return res;
}

async function forward(req: NextRequest, segments: string[]): Promise<NextResponse> {
  const token = req.cookies.get("automata_token")?.value;
  if (!token) {
    return new NextResponse("Não autorizado", { status: 401 });
  }

  try {
    const claims = decodeJwt(token);
    const now = Math.floor(Date.now() / 1000);
    if (claims.exp !== undefined && claims.exp < now) {
      return expiredResponse();
    }
  } catch {
    return new NextResponse("Token inválido", { status: 401 });
  }

  const path = segments.join("/");
  const search = req.nextUrl.search;
  const target = path.startsWith("v1/")
    ? `${API_URL}/api/${path}${search}`
    : `${API_URL}/${path}${search}`;

  const headers = new Headers(req.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.delete("host");

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : req.body,
    // @ts-expect-error — duplex necessário para body streaming no Node
    duplex: "half",
  });

  if (upstream.status === 401) {
    return expiredResponse();
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: upstream.headers,
  });
}

type RouteContext = { params: Promise<{ proxy: string[] }> };

export async function GET(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).proxy);
}
export async function POST(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).proxy);
}
export async function PUT(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).proxy);
}
export async function PATCH(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).proxy);
}
export async function DELETE(req: NextRequest, ctx: RouteContext) {
  return forward(req, (await ctx.params).proxy);
}
