import { describe, expect, it } from "vitest";
import { parseSseBlock, readSse } from "@/lib/sse";

function stream(text: string): ReadableStream<Uint8Array> {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(c) {
      // corta no meio de um evento para testar o buffer
      c.enqueue(bytes.slice(0, 20));
      c.enqueue(bytes.slice(20));
      c.close();
    },
  });
}

describe("sse", () => {
  it("lê evento e dados", () => {
    expect(parseSseBlock('event: RunContent\ndata: {"content":"oi"}')).toEqual({
      event: "RunContent",
      data: { content: "oi" },
    });
  });

  it("ignora bloco sem dados ou com JSON inválido", () => {
    expect(parseSseBlock("event: RunStarted")).toBeNull();
    expect(parseSseBlock("data: {quebrado")).toBeNull();
  });

  it("junta eventos quebrados entre chunks", async () => {
    const events = [];
    for await (const e of readSse(
      stream(
        'event: RunStarted\ndata: {"session_id":"s"}\n\nevent: RunContent\ndata: {"content":"a"}\n\n',
      ),
    )) {
      events.push(e.event);
    }
    expect(events).toEqual(["RunStarted", "RunContent"]);
  });
});
