import type { NextRequest } from "next/server";

// Cabeçalhos de encaminhamento enviados pelo browser não podem chegar à API:
// ela decide o IP do rate limit a partir deles (TRUSTED_PROXIES).
export const FORWARDING_HEADERS = ["x-forwarded-for", "x-real-ip", "forwarded"];

// De onde vem o IP do cliente. Só a borda na frente do Next sabe o IP de verdade:
// - "x-real-ip": o valor que a borda sobrescreve (padrão no Vercel);
// - "x-forwarded-for": o último hop, que o proxy reverso próprio acrescenta;
// - vazio: Next exposto direto, nenhum cabeçalho é confiável e nada é repassado.
// Ler o primeiro hop ou o x-real-ip sem proxy deixava o cliente escolher o IP do
// rate limit de login a cada tentativa.
function source(): string {
  const configured = process.env.CLIENT_IP_HEADER?.trim().toLowerCase();
  if (configured) return configured;
  return process.env.VERCEL ? "x-real-ip" : "";
}

export function clientIp(req: NextRequest): string | null {
  const header = source();
  if (header === "x-real-ip") return req.headers.get("x-real-ip")?.trim() || null;
  if (header === "x-forwarded-for") {
    const hops = req.headers.get("x-forwarded-for")?.split(",") ?? [];
    return hops.at(-1)?.trim() || null;
  }
  return null;
}
