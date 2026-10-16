// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/auth/logout/route";

function request(cookie?: string) {
  return new NextRequest("http://localhost:3000/api/auth/logout", {
    method: "POST",
    headers: cookie ? { cookie } : {},
  });
}

describe("POST /api/auth/logout", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("revoga o token na API e apaga o cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const res = await POST(request("automata_token=abc"));

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/v1/auth/logout", {
      method: "POST",
      headers: { Authorization: "Bearer abc" },
    });
    expect(res.headers.get("set-cookie")).toMatch(/automata_token=;/);
  });

  it("apaga o cookie mesmo com a API fora do ar", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("ECONNREFUSED")));

    const res = await POST(request("automata_token=abc"));

    expect(res.status).toBe(200);
    expect(res.headers.get("set-cookie")).toMatch(/automata_token=;/);
  });

  it("sem cookie não chama a API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await POST(request());

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
