import type { NextResponse } from "next/server";

// mesmo cookie do login, da troca de senha e do link de recuperação
// httpOnly: o JS da página nunca lê o token; secure só em produção, para o dev em http
export function setSessionCookie(response: NextResponse, token: string): void {
  response.cookies.set("automata_token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
}
