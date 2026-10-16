"use client";

import { useRef, useState } from "react";
import { type KnowledgeSource, mergeSources, sourcesFromTool } from "@/lib/knowledge-sources";
import { readSse } from "@/lib/sse";
import { Button } from "@/components/ui/button";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  // documentos das bases de conhecimento consultadas para esta resposta
  sources?: KnowledgeSource[];
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
  // time usa as rotas /teams e eventos TeamRun*; membros aparecem no rastro
  kind?: "agent" | "team";
  memberNames?: Record<string, string>;
}

interface TraceStep {
  id: number;
  text: string;
}

interface ToolEventData {
  tool_name?: string | null;
  tool_args?: Record<string, unknown> | null;
  result?: unknown;
}

function describeTool(tool: ToolEventData | undefined, names: Record<string, string>): string {
  const args = tool?.tool_args ?? {};
  if (tool?.tool_name === "delegate_task_to_member") {
    const member = String(args.member_id ?? "");
    return `Delegou a ${names[member] ?? member}: ${String(args.task ?? "")}`;
  }
  if (tool?.tool_name === "delegate_task_to_members") {
    return `Delegou a todos: ${String(args.task ?? "")}`;
  }
  return `Chamou ${tool?.tool_name ?? "tool"}`;
}

export function TestPanel({
  agentId,
  draftVersionId,
  defaultOpen = false,
  kind = "agent",
  memberNames = {},
}: Props) {
  const base = kind === "team" ? "teams" : "agents";
  const prefix = kind === "team" ? "Team" : "";
  const [trace, setTrace] = useState<TraceStep[]>([]);
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

  function addSources(tool: ToolEventData | undefined) {
    const found = sourcesFromTool(tool);
    if (found.length === 0) return;
    setMessages((prev) => {
      const copy = [...prev];
      const last = copy[copy.length - 1];
      if (!last || last.role !== "assistant") return prev;
      copy[copy.length - 1] = { ...last, sources: mergeSources(last.sources ?? [], found) };
      return copy;
    });
  }

  async function consume(res: Response) {
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    for await (const { event, data } of readSse(res.body)) {
      if (typeof data.session_id === "string" && (kind !== "team" || !data.agent_id)) {
        sessionIdRef.current = data.session_id;
      }
      const memberEvent = kind === "team" && typeof data.agent_id === "string";
      if (memberEvent) {
        // membro trabalhando: vai para o rastro, não para a resposta do time
        if (event === "ToolCallStarted") {
          const who = memberNames[data.agent_id as string] ?? String(data.agent_name ?? "membro");
          addTrace(`${who}: ${describeTool(data.tool as ToolEventData, memberNames)}`);
        } else if (event === "ToolCallCompleted") {
          addSources(data.tool as ToolEventData);
        }
        continue;
      }
      if (kind === "team" && event === "TeamToolCallStarted") {
        addTrace(describeTool(data.tool as ToolEventData, memberNames));
      } else if (event === `${prefix}ToolCallCompleted`) {
        addSources(data.tool as ToolEventData);
      } else if (event === `${prefix}RunContent` && typeof data.content === "string") {
        appendToLast(data.content);
      } else if (event === `${prefix}RunPaused`) {
        const tools = ((data.tools as PendingToolExecution[] | undefined) ?? []).filter(
          (t) => t.requires_confirmation && t.confirmed == null,
        );
        if (typeof data.run_id === "string" && tools.length > 0) {
          setPaused({ runId: data.run_id, tools });
        }
      } else if (event === `${prefix}RunError`) {
        setError(typeof data.content === "string" ? data.content : "Erro ao executar agente.");
      }
    }
  }

  function addTrace(text: string) {
    setTrace((prev) => [...prev, { id: nextId.current++, text }]);
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
    setTrace([]);
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
    await run(() => fetch(`/api/${base}/${agentId}/runs`, { method: "POST", body: form }));
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
      fetch(`/api/${base}/${agentId}/runs/${runId}/continue`, { method: "POST", body: form }),
    );
  }

  function clearSession() {
    setMessages([]);
    setTrace([]);
    setPaused(null);
    sessionIdRef.current = null;
    setError(null);
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-[13px] font-medium">Modo teste</h2>
        <Button onClick={() => setOpen((o) => !o)} variant="muted" size="sm">
          {open ? "Fechar" : "Abrir chat"}
        </Button>
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
                {m.sources && m.sources.length > 0 && (
                  <ul aria-label="Fontes" className="flex max-w-xs flex-col gap-0.5 text-[11px]">
                    {m.sources.map((src) => (
                      <li key={`${src.base}|${src.documento}`} className="text-muted-foreground">
                        <span className="text-[var(--text-label)]">fonte</span> {src.documento}
                        {src.base && <span> · {src.base}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>

          {trace.length > 0 && (
            <ol aria-label="Rastro de delegação" className="flex flex-col gap-1 text-[12px]">
              {trace.map((step) => (
                <li key={step.id} className="text-muted-foreground">
                  → {step.text}
                </li>
              ))}
            </ol>
          )}

          {paused && (
            <div
              role="alertdialog"
              aria-label="Confirmação de ferramenta"
              className="flex flex-col gap-2 rounded border border-amber-500/50 p-3"
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
                <Button onClick={() => void decide(true)} variant="strong">
                  Aprovar
                </Button>
                <Button onClick={() => void decide(false)} variant="destructive">
                  Rejeitar
                </Button>
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
            <Button
              onClick={() => void sendMessage()}
              disabled={isRunning || paused !== null || !input.trim()}
              variant="strong"
            >
              {isRunning ? "…" : "Enviar"}
            </Button>
            {messages.length > 0 && (
              <Button onClick={clearSession} disabled={isRunning} variant="muted">
                Limpar
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
