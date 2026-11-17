// @vitest-environment node
import { exportSPKI, generateKeyPair, SignJWT } from "jose";
import { NextRequest } from "next/server";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as change } from "@/app/api/auth/password/route";
import { POST as reset } from "@/app/api/auth/password/reset/route";
import { proxy } from "@/proxy";

type Pair = Awaited<ReturnType<typeof generateKeyPair>>;
let pair: Pair;

beforeAll(async () => {
  pair = await generateKeyPair("RS256", { extractable: true });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

async function token(claims: Record<string, unknown>) {
  return new SignJWT(claims)
    .setProtectedHeader({ alg: "RS256" })
    .setSubject("u1")
    .setAudience("automata")
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(pair.privateKey);
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("senha provisória e recuperação (ADR-0045)", () => {
  it("token de senha provisória só abre a página de troca", async () => {
    vi.stubEnv("JWT_PUBLIC_KEY", await exportSPKI(pair.publicKey));
    const provisorio = await token({ scopes: [], must_change_password: true });
    const req = (path: string) =>
      new NextRequest(`http://painel${path}`, {
        headers: { cookie: `automata_token=${provisorio}` },
      });

    const res = await proxy(req("/agents"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("http://painel/trocar-senha?obrigatoria=1");
    expect((await proxy(req("/trocar-senha?obrigatoria=1"))).headers.get("location")).toBeNull();

    const normal = await token({ scopes: ["configs:read"] });
    const ok = await proxy(
      new NextRequest("http://painel/agents", { headers: { cookie: `automata_token=${normal}` } }),
    );
    expect(ok.headers.get("location")).toBeNull();
  });

  it("recuperação abre sem sessão", async () => {
    vi.stubEnv("JWT_PUBLIC_KEY", await exportSPKI(pair.publicKey));
    for (const path of ["/esqueci-senha", "/redefinir-senha?token=x"]) {
      const res = await proxy(new NextRequest(`http://painel${path}`));
      expect(res.headers.get("location")).toBeNull();
    }
  });

  it("login repassa a troca obrigatória ao painel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ access_token: "t", must_change_password: true })),
    );
    const res = await login(
      new NextRequest("http://painel/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "a@b.com", password: "x" }),
      }),
    );
    expect(await res.json()).toEqual({ ok: true, must_change_password: true });
    expect(res.cookies.get("automata_token")?.value).toBe("t");
  });

  it("troca leva o token da sessão e grava o token novo", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ access_token: "novo" }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await change(
      new NextRequest("http://painel/api/auth/password", {
        method: "POST",
        headers: { cookie: "automata_token=velho" },
        body: JSON.stringify({ current_password: "a", new_password: "b" }),
      }),
    );
    expect(res.status).toBe(200);
    expect(res.cookies.get("automata_token")?.value).toBe("novo");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/me/password");
    expect(init.headers.Authorization).toBe("Bearer velho");
  });

  it("link vencido devolve o motivo sem gravar cookie", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "Link inválido ou vencido. Peça outro." }, 400)),
    );
    const res = await reset(
      new NextRequest("http://painel/api/auth/password/reset", {
        method: "POST",
        body: JSON.stringify({ token: "x", new_password: "y" }),
      }),
    );
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ detail: "Link inválido ou vencido. Peça outro." });
    expect(res.cookies.get("automata_token")).toBeUndefined();
  });
});
