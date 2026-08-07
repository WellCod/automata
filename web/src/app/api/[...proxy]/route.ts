import { NextRequest, NextResponse } from "next/server";
import { issueToken } from "@/lib/bff/token";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";
const PANEL_USER_ID = process.env.PANEL_USER_ID ?? "panel";
const PANEL_SCOPES = ["agent_os:admin"];

async function forward(req: NextRequest, segments: string[]): Promise<NextResponse> {
  const token = await issueToken(PANEL_USER_ID, PANEL_SCOPES);
  const path = segments.join("/");
  const search = req.nextUrl.search;
  const target = `${API_URL}/api/${path}${search}`;

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
