// @vitest-environment node
import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GET, POST } from "@/app/hooks/channels/[id]/route";

const ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const ctx = (id: string) => ({ params: Promise.resolve({ id }) });

afterEach(() => vi.unstubAllGlobals());

describe("webhook dos canais no painel", () => {
  it("repassa o corpo cru e a assinatura à API, sem cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const body = '{"entry":[]}';
    const res = await POST(
      new NextRequest(`http://painel/hooks/channels/${ID}`, {
        method: "POST",
        body,
        headers: {
          "content-type": "application/json",
          "x-hub-signature-256": "sha256=abc",
          cookie: "automata_token=nao-vai",
        },
      }),
      ctx(ID),
    );
    expect(res.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`http://localhost:8000/hooks/channels/${ID}`);
    expect(new TextDecoder().decode(init.body)).toBe(body);
    expect(init.headers["x-hub-signature-256"]).toBe("sha256=abc");
    expect(init.headers.cookie).toBeUndefined();
    expect(init.headers.authorization).toBeUndefined();
  });

  it("verificação do WhatsApp leva a query e devolve o desafio", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response("42", { headers: { "Content-Type": "text/plain" } }));
    vi.stubGlobal("fetch", fetchMock);
    const res = await GET(
      new NextRequest(
        `http://painel/hooks/channels/${ID}?hub.mode=subscribe&hub.verify_token=t&hub.challenge=42`,
      ),
      ctx(ID),
    );
    expect(await res.text()).toBe("42");
    expect(fetchMock.mock.calls[0][0]).toContain("?hub.mode=subscribe");
  });

  it("id que não é uuid não chega à API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const res = await POST(
      new NextRequest("http://painel/hooks/channels/..%2F..%2Fapi", { method: "POST" }),
      ctx("../../api"),
    );
    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
