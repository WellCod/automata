// Leitura de SSE do AgentOS. O Agno nomeia eventos em CamelCase
// (`RunStarted`, `RunContent`, `RunPaused`…), via `event.event`.

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

export function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (data.length === 0) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) as Record<string, unknown> };
  } catch {
    return null;
  }
}

export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let sep = buf.indexOf("\n\n");
    while (sep !== -1) {
      const parsed = parseSseBlock(buf.slice(0, sep));
      buf = buf.slice(sep + 2);
      if (parsed) yield parsed;
      sep = buf.indexOf("\n\n");
    }
  }
  const tail = parseSseBlock(buf);
  if (tail) yield tail;
}
