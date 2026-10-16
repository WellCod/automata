import { afterEach, describe, expect, it, vi } from "vitest";

async function headersFor(nodeEnv: string): Promise<Record<string, string>> {
  vi.stubEnv("NODE_ENV", nodeEnv);
  vi.resetModules();
  const { default: config } = await import("../../next.config");
  const rules = await config.headers!();
  return Object.fromEntries(rules[0].headers.map((h) => [h.key, h.value]));
}

describe("headers de segurança do painel", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("produção envia CSP sem unsafe-eval e HSTS", async () => {
    const headers = await headersFor("production");
    const csp = headers["Content-Security-Policy"];
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("connect-src 'self'");
    expect(csp).not.toContain("unsafe-eval");
    expect(headers["Strict-Transport-Security"]).toMatch(/^max-age=\d+/);
  });

  it("dev libera unsafe-eval e não envia HSTS", async () => {
    const headers = await headersFor("development");
    expect(headers["Content-Security-Policy"]).toContain("'unsafe-eval'");
    expect(headers["Strict-Transport-Security"]).toBeUndefined();
  });
});
