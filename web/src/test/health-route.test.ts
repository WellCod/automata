// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET } from "@/app/api/health/route";
import { proxy } from "@/proxy";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("health do painel (OPS-05)", () => {
  it("abre sem sessão e repassa o estado da API com a versão do painel", async () => {
    vi.stubEnv("AUTOMATA_VERSION", "v1.2.3");
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ status: "ok", version: "v1.2.3", migration: "0060" })),
        ),
    );
    const open = await proxy(new NextRequest("http://painel/api/health"));
    expect(open.headers.get("location")).toBeNull();

    const res = await GET();
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({
      status: "ok",
      api: { migration: "0060" },
      panel: { version: "v1.2.3" },
    });
  });

  it("API fora vira 503", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const res = await GET();
    expect(res.status).toBe(503);
    expect((await res.json()).status).toBe("degraded");
  });
});
