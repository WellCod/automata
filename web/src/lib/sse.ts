// Leitura de SSE do AgentOS. O Agno nomeia eventos em CamelCase
// (`RunStarted`, `RunContent`, `RunPaused`…), via `event.event`.

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

// Um bloco é o texto entre duas linhas em branco. Sem `event:`, o padrão do SSE é
// "message"; bloco sem `data:` (comentário, keep-alive) ou com JSON quebrado é ignorado.
export function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) as Record<string, unknown> };
  } catch {
    return null;
  }
}

// Um pedaço lido do stream pode cortar um bloco no meio: o resto fica no buffer até o
// próximo pedaço, e o que sobrar no fim do stream é lido como último bloco.
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let separatorIndex = buffer.indexOf("\n\n");
    while (separatorIndex !== -1) {
      const parsed = parseSseBlock(buffer.slice(0, separatorIndex));
      buffer = buffer.slice(separatorIndex + 2);
      if (parsed) yield parsed;
      separatorIndex = buffer.indexOf("\n\n");
    }
  }
  const tail = parseSseBlock(buffer);
  if (tail) yield tail;
}
