// @vitest-environment node
import { SignJWT } from "jose";
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/api/[...proxy]/route";

afterEach(() => vi.unstubAllGlobals());

async function token(): Promise<string> {
  const exp = Math.floor(Date.now() / 1000) + 3600;
  return new SignJWT({ exp }).setProtectedHeader({ alg: "HS256" }).sign(new Uint8Array(32));
}

function req(path: string, cookie: string, method = "GET"): NextRequest {
  return new NextRequest(`http://painel/api/${path}`, {
    method,
    headers: { cookie: `automata_token=${cookie}` },
  });
}

const ctx = (segments: string[]) => ({ params: Promise.resolve({ proxy: segments }) });

describe("proxy genérico do BFF", () => {
  it.each([
    ["v1/auth/login", ["v1", "auth", "login"]],
    ["api/v1/auth/login", ["api", "v1", "auth", "login"]],
    ["api/v1/auth/users", ["api", "v1", "auth", "users"]],
    ["API/v1/auth/login", ["API", "v1", "auth", "login"]],
  ])("não alcança as rotas de auth da API por %s", async (path, segments) => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(req(path, await token(), "POST"), ctx(segments));
    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("repassa as rotas próprias com o token no Authorization", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const t = await token();
    const res = await GET(req("v1/configs", t), ctx(["v1", "configs"]));
    expect(res.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/configs");
    expect(init.headers.get("authorization")).toBe(`Bearer ${t}`);
  });
});
