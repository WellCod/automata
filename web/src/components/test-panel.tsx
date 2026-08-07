"use client";

import { useRef, useState } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  agentId: string;
  draftVersionId?: string;
  defaultOpen?: boolean;
}

export function TestPanel({ agentId, draftVersionId, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [useDraft, setUseDraft] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  async function sendMessage() {
    if (!input.trim() || isRunning) return;
    const text = input.trim();
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
    setIsRunning(true);

    try {
      const form = new FormData();
      form.append("message", text);
      form.append("stream", "true");
      if (sessionIdRef.current) form.append("session_id", sessionIdRef.current);
      if (useDraft && draftVersionId) {
        form.append("factory_input", JSON.stringify({ version_id: draftVersionId }));
      }

      const res = await fetch(`/api/agents/${agentId}/runs`, {
        method: "POST",
        body: form,
      });

      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      const flush = (lines: string[]) => {
        let eventType = "";
        let dataLine = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            dataLine = line.slice(6).trim();
          } else if (line === "" && dataLine) {
            if (eventType === "run_started") {
              try {
                const evt = JSON.parse(dataLine) as { session_id?: string };
                if (evt.session_id) sessionIdRef.current = evt.session_id;
              } catch {}
            } else if (eventType === "run_content") {
              try {
                const evt = JSON.parse(dataLine) as { content?: string };
                if (typeof evt.content === "string") {
                  setMessages((prev) => {
                    const copy = [...prev];
                    const last = copy[copy.length - 1];
                    copy[copy.length - 1] = {
                      ...last,
                      content: last.content + evt.content,
                    };
                    return copy;
                  });
                }
              } catch {}
            }
            eventType = "";
            dataLine = "";
          }
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        flush(lines);
      }
      if (buf) flush([buf, ""]);
    } catch {
      setError("Erro ao executar agente.");
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: "[Falha na execução]" };
        return copy;
      });
    } finally {
      setIsRunning(false);
    }
  }

  function clearSession() {
    setMessages([]);
    sessionIdRef.current = null;
    setError(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-muted-foreground text-[11px] font-medium tracking-[0.05em] uppercase">
          Modo Teste
        </span>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground rounded border px-2 py-1 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors"
        >
          {open ? "Fechar" : "Abrir chat"}
        </button>
      </div>

      {open && (
        <div className="flex flex-col gap-2">
          {draftVersionId && (
            <label className="text-muted-foreground flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={useDraft}
                onChange={(e) => setUseDraft(e.target.checked)}
                className="h-3.5 w-3.5 accent-[var(--accent)]"
              />
              Testar rascunho
            </label>
          )}

          <div className="border-border bg-card flex max-h-72 min-h-24 flex-col gap-2 overflow-y-auto rounded border p-3">
            {messages.length === 0 && (
              <p className="text-muted-foreground text-[13px]">Nenhuma mensagem ainda.</p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex flex-col gap-0.5 ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
                  {m.role === "user" ? "Você" : "Agente"}
                </span>
                <div
                  className={`max-w-[240px] rounded border px-3 py-1.5 text-[13px] ${
                    m.role === "user"
                      ? "border-foreground/20 bg-muted text-foreground"
                      : "border-border bg-background text-foreground"
                  }`}
                >
                  {m.content || (isRunning && m.role === "assistant" ? "▍" : "")}
                </div>
              </div>
            ))}
          </div>

          {error && <p className="text-destructive text-[11px]">{error}</p>}

          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void sendMessage()}
              placeholder="Digite uma mensagem…"
              disabled={isRunning}
              className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent flex-1 rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] transition-colors focus:outline-none disabled:opacity-40"
            />
            <button
              type="button"
              onClick={() => void sendMessage()}
              disabled={isRunning || !input.trim()}
              className="border-foreground text-foreground hover:border-accent hover:text-accent rounded border px-3 py-1.5 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
            >
              {isRunning ? "…" : "Enviar"}
            </button>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearSession}
                disabled={isRunning}
                className="border-border text-muted-foreground hover:border-foreground/40 hover:text-foreground rounded border px-3 py-1.5 text-[11px] tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
              >
                Limpar
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
