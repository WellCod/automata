import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.AUTOMATA_API_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  const token = req.cookies.get("automata_token")?.value;
  if (token) {
    // Revoga o jti na API; se ela estiver fora, o cookie sai mesmo assim e o
    // token expira sozinho
    try {
      await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {}
  }

  const res = NextResponse.json({ ok: true });
  res.cookies.delete("automata_token");
  return res;
}
