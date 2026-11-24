import { errors, importSPKI, type JWTPayload, jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

const ALG = "RS256";
const AUDIENCE = process.env.JWT_AUDIENCE ?? "automata";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

// CSRF por Origin (PR 44): mutação cuja Origin não é o host do painel volta 403.
// Sem Origin passa, porque o navegador manda o cabeçalho nas requisições de mutação;
// quem chega sem ele não é um formulário de outro site carregando o cookie da sessão.
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
  const pemKeys = previous ? [current, previous] : [current];
  return Promise.all(pemKeys.map((pem) => importSPKI(pem, ALG)));
}

// Só assinatura inválida passa para a próxima chave; vencido falha na chave certa
export async function verifyToken(token: string): Promise<JWTPayload> {
  const keys = await getPublicKeys();
  for (const [index, key] of keys.entries()) {
    try {
      const { payload } = await jwtVerify(token, key, { audience: AUDIENCE });
      return payload;
    } catch (err) {
      const isLastKey = index === keys.length - 1;
      if (isLastKey || !(err instanceof errors.JWSSignatureVerificationFailed)) throw err;
    }
  }
  throw new Error("nenhuma chave pública");
}

// páginas abertas sem sessão: login e recuperação de senha (ADR-0045)
const PUBLIC_PAGES = ["/login", "/esqueci-senha", "/redefinir-senha"];

// Proxy do Next (antigo middleware): roda antes de toda página e de toda rota do BFF.
// Confere a assinatura do JWT do cookie; as rotas de /api/[...proxy] confiam nisso e
// só olham o vencimento antes de repassar o token à API como Bearer.
export async function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const csrfError = csrfCheck(req);
  if (csrfError) return csrfError;

  if (
    PUBLIC_PAGES.some((page) => pathname.startsWith(page)) ||
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
    // token vencido, de outra chave ou adulterado: o cookie sai para o login não voltar aqui
    const response = NextResponse.redirect(new URL("/login", req.url));
    response.cookies.delete("automata_token");
    return response;
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
