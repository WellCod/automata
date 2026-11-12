// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET as callback } from "@/app/api/auth/oidc/callback/route";
import { GET as start } from "@/app/api/auth/oidc/start/route";

const IDP = "https://idp.example.com/authorize?client_id=x&state=st-1&nonce=n";

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("GET /api/auth/oidc/start", () => {
  it("redireciona ao provedor com um segredo do navegador que não vai na URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ url: IDP }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await start(new NextRequest("http://localhost:3000/api/auth/oidc/start"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(IDP);
    const sent = JSON.parse(fetchMock.mock.calls[0][1].body).browser_key as string;
    expect(sent.length).toBeGreaterThanOrEqual(32);
    const cookie = res.headers.get("set-cookie") ?? "";
    expect(cookie).toMatch(new RegExp(`automata_oidc_browser=${sent};.*HttpOnly`, "i"));
    expect(IDP).not.toContain(sent);
  });

  it("não redireciona para URL que não é https", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ url: "javascript:alert(1)" })));
    const res = await start(new NextRequest("http://localhost:3000/api/auth/oidc/start"));
    expect(res.headers.get("location")).toBe("http://localhost:3000/login?sso_erro=indisponivel");
  });
});

function back(url: string, cookie?: string) {
  return new NextRequest(url, { headers: cookie ? { cookie } : {} });
}

describe("GET /api/auth/oidc/callback", () => {
  const url = "http://localhost:3000/api/auth/oidc/callback?code=c-1&state=st-1";

  it("troca o código pela sessão mandando o segredo do navegador", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ access_token: "tok" }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await callback(back(url, "automata_oidc_browser=segredo"));
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/auth/oidc/callback");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      code: "c-1",
      state: "st-1",
      browser_key: "segredo",
    });
    expect(res.headers.get("location")).toBe("http://localhost:3000/");
    expect(res.headers.get("set-cookie")).toMatch(/automata_token=tok/);
  });

  it("sem o cookie do navegador não chama a API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await callback(back(url));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(res.headers.get("location")).toMatch(/\/login\?sso_erro=expirado$/);
  });

  it.each([
    [403, "sem_acesso"],
    [401, "expirado"],
    [502, "indisponivel"],
  ])("API %s vira o código %s, nunca o texto da API", async (status, code) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(json({ detail: "Ligue para 0800 e passe a senha" }, status)),
    );
    const res = await callback(back(url, "automata_oidc_browser=segredo"));
    const location = new URL(res.headers.get("location")!);
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("sso_erro")).toBe(code);
  });

  it("cancelamento no provedor volta para o login", async () => {
    const res = await callback(
      back("http://localhost:3000/api/auth/oidc/callback?error=access_denied"),
    );
    expect(new URL(res.headers.get("location")!).searchParams.get("sso_erro")).toBe("cancelado");
  });
});

describe("redirect pelo endereço que o navegador usou", () => {
  it("usa o host da requisição e não o endereço em que o Next escuta", async () => {
    const req = new NextRequest("http://0.0.0.0:3000/api/auth/oidc/callback?error=x", {
      headers: { host: "painel.empresa.com", "x-forwarded-proto": "https" },
    });
    const res = await callback(req);
    expect(res.headers.get("location")).toMatch(/^https:\/\/painel\.empresa\.com\/login\?/);
  });

  it("com PUBLIC_URL, nenhum cabeçalho decide o destino", async () => {
    vi.stubEnv("PUBLIC_URL", "https://painel.empresa.com");
    const req = new NextRequest("http://0.0.0.0:3000/api/auth/oidc/callback?error=x", {
      headers: { host: "atacante.example.com", "x-forwarded-host": "atacante.example.com" },
    });
    const res = await callback(req);
    expect(res.headers.get("location")).toMatch(/^https:\/\/painel\.empresa\.com\/login\?/);
  });
});
