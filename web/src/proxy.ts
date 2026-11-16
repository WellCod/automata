import { errors, importSPKI, type JWTPayload, jwtVerify } from "jose";
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
export async function verifyToken(token: string): Promise<JWTPayload> {
  const keys = await getPublicKeys();
  for (const [i, key] of keys.entries()) {
    try {
      const { payload } = await jwtVerify(token, key, { audience: AUDIENCE });
      return payload;
    } catch (err) {
      const last = i === keys.length - 1;
      if (last || !(err instanceof errors.JWSSignatureVerificationFailed)) throw err;
    }
  }
  throw new Error("nenhuma chave pública");
}

// páginas abertas sem sessão: login e recuperação de senha (ADR-0045)
const PUBLIC_PAGES = ["/login", "/esqueci-senha", "/redefinir-senha"];

export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const csrfError = csrfCheck(req);
  if (csrfError) return csrfError;

  if (
    PUBLIC_PAGES.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/api/auth/") ||
    // monitor externo da instância (OPS-05)
    pathname === "/api/health"
  ) {
    return NextResponse.next();
  }
  // webhook dos canais (ADR-0044): quem chama é o provedor, e a API confere a assinatura
  if (pathname.startsWith("/hooks/channels/")) {
    return NextResponse.next();
  }

  const token = req.cookies.get("automata_token")?.value;

  if (!token) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  let claims: JWTPayload;
  try {
    claims = await verifyToken(token);
  } catch {
    const res = NextResponse.redirect(new URL("/login", req.url));
    res.cookies.delete("automata_token");
    return res;
  }

  // senha provisória: o token não tem scope e só serve para a troca
  if (
    claims.must_change_password === true &&
    !pathname.startsWith("/trocar-senha") &&
    !pathname.startsWith("/api/")
  ) {
    return NextResponse.redirect(new URL("/trocar-senha?obrigatoria=1", req.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
