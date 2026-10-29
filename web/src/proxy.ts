import { errors, importSPKI, jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

const ALG = "RS256";
const AUDIENCE = process.env.JWT_AUDIENCE ?? "automata";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function csrfCheck(req: NextRequest): NextResponse | null {
  if (SAFE_METHODS.has(req.method)) return null;
  const origin = req.headers.get("origin");
  if (!origin) return null;
  const host = req.headers.get("host");
  try {
    if (new URL(origin).host !== host) {
      return new NextResponse("Origem não permitida", { status: 403 });
    }
  } catch {
    return new NextResponse("Origem inválida", { status: 403 });
  }
  return null;
}

// Atual primeiro; a anterior só existe durante a rotação da chave (ADR-0026)
async function getPublicKeys() {
  const current = process.env.JWT_PUBLIC_KEY;
  if (!current) throw new Error("JWT_PUBLIC_KEY não definida");
  const previous = process.env.JWT_PREVIOUS_PUBLIC_KEY;
  const raws = previous ? [current, previous] : [current];
  return Promise.all(raws.map((raw) => importSPKI(raw, ALG)));
}

// Só assinatura inválida passa para a próxima chave; vencido falha na chave certa
export async function verifyToken(token: string): Promise<void> {
  const keys = await getPublicKeys();
  for (const [i, key] of keys.entries()) {
    try {
      await jwtVerify(token, key, { audience: AUDIENCE });
      return;
    } catch (err) {
      const last = i === keys.length - 1;
      if (last || !(err instanceof errors.JWSSignatureVerificationFailed)) throw err;
    }
  }
}

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const csrfError = csrfCheck(req);
  if (csrfError) return csrfError;

  if (pathname.startsWith("/login") || pathname.startsWith("/api/auth/")) {
    return NextResponse.next();
  }

  const token = req.cookies.get("automata_token")?.value;

  if (!token) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  try {
    await verifyToken(token);
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
