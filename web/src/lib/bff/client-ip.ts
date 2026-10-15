import type { NextRequest } from "next/server";

// Cabeçalhos de encaminhamento enviados pelo browser não podem chegar à API:
// ela decide o IP do rate limit a partir deles (TRUSTED_PROXIES).
export const FORWARDING_HEADERS = ["x-forwarded-for", "x-real-ip", "forwarded"];

// IP do cliente como visto pela borda (Vercel ou proxy reverso), que sobrescreve
// esses cabeçalhos. Sem proxy na frente do Next o valor é do cliente e a API
// só deve confiar no BFF se houver um.
export function clientIp(req: NextRequest): string | null {
  const real = req.headers.get("x-real-ip");
  if (real) return real.trim();
  const forwarded = req.headers.get("x-forwarded-for");
  return forwarded ? forwarded.split(",")[0].trim() : null;
}
