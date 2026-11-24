import { decodeJwt } from "jose";
import { NextRequest, NextResponse } from "next/server";

import { FORWARDING_HEADERS } from "@/lib/bff/client-ip";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

// 401 com o cookie apagado: o painel trata como sessão encerrada e volta ao login
function expiredResponse(): NextResponse {
  const response = new NextResponse("Sessão expirada", { status: 401 });
  response.cookies.delete("automata_token");
  return response;
}

/** Repassa a chamada do painel à API, trocando o cookie de sessão pelo Bearer. */
async function forward(req: NextRequest, segments: string[]): Promise<NextResponse> {
  const token = req.cookies.get("automata_token")?.value;
  if (!token) {
    return new NextResponse("Não autorizado", { status: 401 });
  }

  // decodeJwt não confere a assinatura: quem confere é o proxy.ts, antes de a requisição
  // chegar aqui. Este teste só evita repassar à API um token que já venceu (PR 42)
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
  // o client gerado chama /api/api/v1/... e chega como api/v1/...; quem chama /api/v1/...
  // direto chega como v1/... e ganha o prefixo; o resto (rotas do AgentOS) vai como veio
  const apiPath = path.startsWith("v1/") ? `api/${path}` : path;
  // login, logout e SSO têm rotas próprias, que repassam o IP do cliente ao rate limit;
  // pelo proxy genérico chegariam à API como se viessem do painel
  if (apiPath.toLowerCase().startsWith("api/v1/auth/")) {
    return new NextResponse("Não encontrado", { status: 404 });
  }
  const target = `${API_URL}/${apiPath}${req.nextUrl.search}`;

  const headers = new Headers(req.headers);
  headers.set("Authorization", `Bearer ${token}`);
  headers.delete("host");
  // O cookie de sessão já virou Authorization; a API não precisa dele
  headers.delete("cookie");
  // o IP de rate limit não pode vir do navegador (ver lib/bff/client-ip.ts)
  for (const name of FORWARDING_HEADERS) headers.delete(name);

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : req.body,
    // @ts-expect-error — duplex necessário para body streaming no Node
    duplex: "half",
  });

  // a API recusou o token (revogado no logout, usuário removido, sessão cortada)
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
