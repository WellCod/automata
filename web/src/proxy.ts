import { importSPKI, jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

const ALG = "RS256";
const AUDIENCE = process.env.JWT_AUDIENCE ?? "automata";

async function getPublicKey() {
  const raw = process.env.JWT_PUBLIC_KEY;
  if (!raw) throw new Error("JWT_PUBLIC_KEY não definida");
  return importSPKI(raw, ALG);
}

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith("/login") || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  const token = req.cookies.get("automata_token")?.value;

  if (!token) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  try {
    await jwtVerify(token, await getPublicKey(), { audience: AUDIENCE });
  } catch {
    const res = NextResponse.redirect(new URL("/login", req.url));
    res.cookies.delete("automata_token");
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
