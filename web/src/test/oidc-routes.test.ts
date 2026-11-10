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

afterEach(() => vi.unstubAllGlobals());

describe("GET /api/auth/oidc/start", () => {
  it("redireciona para o provedor e prende o state ao navegador", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ url: IDP })));
    const res = await start(new NextRequest("http://localhost:3000/api/auth/oidc/start"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe(IDP);
    expect(res.headers.get("set-cookie")).toMatch(/automata_oidc_state=st-1;.*HttpOnly/i);
  });

  it("não redireciona para URL que não é https", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ url: "javascript:alert(1)" })));
    const res = await start(new NextRequest("http://localhost:3000/api/auth/oidc/start"));
    expect(res.headers.get("location")).toMatch(/^http:\/\/localhost:3000\/login\?sso_erro=/);
  });
});

function back(url: string, cookie?: string) {
  return new NextRequest(url, { headers: cookie ? { cookie } : {} });
}

describe("GET /api/auth/oidc/callback", () => {
  const url = "http://localhost:3000/api/auth/oidc/callback?code=c-1&state=st-1";

  it("troca o código pela sessão quando o state é deste navegador", async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ access_token: "tok" }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await callback(back(url, "automata_oidc_state=st-1"));
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/api/v1/auth/oidc/callback");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ code: "c-1", state: "st-1" });
    expect(res.headers.get("location")).toBe("http://localhost:3000/");
    expect(res.headers.get("set-cookie")).toMatch(/automata_token=tok/);
  });

  it("recusa state de outro navegador sem chamar a API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await callback(back(url, "automata_oidc_state=outro"));
    expect(fetchMock).not.toHaveBeenCalled();
    expect(res.headers.get("location")).toMatch(/\/login\?sso_erro=/);
    expect(res.headers.get("set-cookie") ?? "").not.toMatch(/automata_token=tok/);
  });

  it("leva a recusa da API para a tela de login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({ detail: "Conta desativada" }, 403)));
    const res = await callback(back(url, "automata_oidc_state=st-1"));
    const location = new URL(res.headers.get("location")!);
    expect(location.pathname).toBe("/login");
    expect(location.searchParams.get("sso_erro")).toBe("Conta desativada");
  });

  it("cancelamento no provedor volta para o login", async () => {
    const res = await callback(
      back("http://localhost:3000/api/auth/oidc/callback?error=access_denied"),
    );
    expect(new URL(res.headers.get("location")!).searchParams.get("sso_erro")).toBe(
      "Login cancelado no provedor",
    );
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
});
