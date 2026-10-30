import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clientIp } from "@/lib/bff/client-ip";

function req(headers: Record<string, string>): NextRequest {
  return new NextRequest("http://localhost/api/auth/login", { headers });
}

const forged = { "x-real-ip": "1.1.1.1", "x-forwarded-for": "6.6.6.6, 3.3.3.3" };

afterEach(() => vi.unstubAllEnvs());

describe("clientIp", () => {
  it("sem proxy configurado não repassa o que o cliente mandou", () => {
    vi.stubEnv("CLIENT_IP_HEADER", "");
    vi.stubEnv("VERCEL", "");
    expect(clientIp(req(forged))).toBeNull();
  });

  it("no Vercel usa o x-real-ip que a borda sobrescreve", () => {
    vi.stubEnv("CLIENT_IP_HEADER", "");
    vi.stubEnv("VERCEL", "1");
    expect(clientIp(req(forged))).toBe("1.1.1.1");
  });

  it("atrás de proxy próprio usa o último hop, que o proxy acrescentou", () => {
    vi.stubEnv("CLIENT_IP_HEADER", "x-forwarded-for");
    expect(clientIp(req(forged))).toBe("3.3.3.3");
  });

  it("retorna null sem o cabeçalho escolhido", () => {
    vi.stubEnv("CLIENT_IP_HEADER", "x-real-ip");
    expect(clientIp(req({}))).toBeNull();
  });
});
