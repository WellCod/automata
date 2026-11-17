import type { NextResponse } from "next/server";

// mesmo cookie do login, da troca de senha e do link de recuperação
export function setSessionCookie(res: NextResponse, token: string): void {
  res.cookies.set("automata_token", token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60,
  });
}
