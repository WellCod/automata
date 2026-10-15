"use client";

import { useRef, useState } from "react";
import { readSse } from "@/lib/sse";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
}

// ToolExecution do Agno, como chega no evento RunPaused e volta no continue
export interface PendingToolExecution {
  tool_call_id?: string | null;
  tool_name?: string | null;
  tool_args?: Record<string, unknown> | null;
  requires_confirmation?: boolean | null;
  confirmed?: boolean | null;
  [key: string]: unknown;
}

interface PausedRun {
  runId: string;
  tools: PendingToolExecution[];
}

interface Props {
  agentId: string;
  draftVersionId?: string;
  defaultOpen?: boolean;
}

const btnCls =
  "inline-flex h-7 items-center rounded border px-3 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40";

export function TestPanel({ agentId, draftVersionId, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [useDraft, setUseDraft] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState<PausedRun | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const nextId = useRef(0);

  function appendToLast(text: string) {
    setMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      copy[copy.length - 1] = { ...last, content: last.content + text };
      return copy;
    });
  }

  async function consume(res: Response) {
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    for await (const { event, data } of readSse(res.body)) {
      if (typeof data.session_id === "string") sessionIdRef.current = data.session_id;
      if (event === "RunContent" && typeof data.content === "string") {
        appendToLast(data.content);
      } else if (event === "RunPaused") {
        const tools = ((data.tools as PendingToolExecution[] | undefined) ?? []).filter(
          (t) => t.requires_confirmation && t.confirmed == null,
        );
        if (typeof data.run_id === "string" && tools.length > 0) {
          setPaused({ runId: data.run_id, tools });
        }
      } else if (event === "RunError") {
        setError(typeof data.content === "string" ? data.content : "Erro ao executar agente.");
      }
    }
  }

  async function run(request: () => Promise<Response>) {
    setIsRunning(true);
    setError(null);
    try {
      await consume(await request());
    } catch {
      setError("Erro ao executar agente.");
    } finally {
      setIsRunning(false);
    }
  }

  async function sendMessage() {
    if (!input.trim() || isRunning || paused) return;
    const text = input.trim();
    setInput("");
    setMessages((prev) => [
      ...prev,
      { id: nextId.current++, role: "user", content: text },
      { id: nextId.current++, role: "assistant", content: "" },
    ]);

    const form = new FormData();
    form.append("message", text);
    form.append("stream", "true");
    if (sessionIdRef.current) form.append("session_id", sessionIdRef.current);
    if (useDraft && draftVersionId) {
      form.append("factory_input", JSON.stringify({ version_id: draftVersionId }));
    }
    await run(() => fetch(`/api/agents/${agentId}/runs`, { method: "POST", body: form }));
  }

  async function decide(approve: boolean) {
    if (!paused || !sessionIdRef.current) return;
    const { runId, tools } = paused;
    setPaused(null);
    const form = new FormData();
    form.append("tools", JSON.stringify(tools.map((t) => ({ ...t, confirmed: approve }))));
    form.append("session_id", sessionIdRef.current);
    form.append("stream", "true");
    await run(() =>
      fetch(`/api/agents/${agentId}/runs/${runId}/continue`, { method: "POST", body: form }),
    );
  }

  function clearSession() {
    setMessages([]);
    setPaused(null);
    sessionIdRef.current = null;
    setError(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-[13px] font-medium">Modo teste</h2>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors"
        >
          {open ? "Fechar" : "Abrir chat"}
        </button>
      </div>

      {open && (
        <div className="flex flex-col gap-3">
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

          <div
            role="log"
            aria-live="polite"
            aria-busy={isRunning}
            className="border-border bg-muted flex max-h-72 min-h-24 flex-col gap-2 overflow-y-auto rounded border p-3"
          >
            {messages.length === 0 && (
              <p className="text-muted-foreground text-[13px]">Nenhuma mensagem ainda.</p>
            )}
            {messages.map((m) => (
              <div
                key={m.id}
                className={`flex flex-col gap-0.5 ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <span className="text-muted-foreground text-[11px]">
                  {m.role === "user" ? "Você" : "Agente"}
                </span>
                <div
                  className={`max-w-xs rounded border px-3 py-1.5 text-[13px] whitespace-pre-wrap ${
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

          {paused && (
            <div
              role="alertdialog"
              aria-label="Confirmação de ferramenta"
              className="flex flex-col gap-2 rounded border border-amber-400/60 p-3"
            >
              <p className="text-foreground text-[13px] font-medium">
                O agente quer executar uma ação que exige confirmação
              </p>
              <ul className="flex flex-col gap-1.5">
                {paused.tools.map((t) => (
                  <li key={t.tool_call_id ?? t.tool_name ?? ""} className="text-[13px]">
                    <code className="text-foreground">{t.tool_name}</code>
                    <pre className="text-muted-foreground mt-1 overflow-x-auto text-[12px]">
                      {JSON.stringify(t.tool_args ?? {}, null, 2)}
                    </pre>
                  </li>
                ))}
              </ul>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void decide(true)}
                  className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
                >
                  Aprovar
                </button>
                <button
                  type="button"
                  onClick={() => void decide(false)}
                  className={`${btnCls} border-destructive text-destructive`}
                >
                  Rejeitar
                </button>
              </div>
            </div>
          )}

          {error && (
            <p className="text-destructive text-[13px]" role="alert">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void sendMessage()}
              placeholder={paused ? "Decida a confirmação acima" : "Digite uma mensagem…"}
              aria-label="Mensagem para o agente"
              disabled={isRunning || paused !== null}
              className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent flex-1 rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] transition-colors focus:outline-none disabled:opacity-40"
            />
            <button
              type="button"
              onClick={() => void sendMessage()}
              disabled={isRunning || paused !== null || !input.trim()}
              className={`${btnCls} border-foreground text-foreground hover:border-accent hover:text-accent`}
            >
              {isRunning ? "…" : "Enviar"}
            </button>
            {messages.length > 0 && (
              <button
                type="button"
                onClick={clearSession}
                disabled={isRunning}
                className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground inline-flex h-7 items-center rounded border px-2 text-[11px] tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
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
