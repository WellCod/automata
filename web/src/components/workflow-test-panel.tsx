"use client";

import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  GitBranch,
  Loader2,
  Repeat,
  ShieldAlert,
  Split,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import { decideWorkflowStep, type StepDecision } from "@/lib/api/approvals";
import { blockLabel } from "@/lib/guardrail-labels";
import { readSse } from "@/lib/sse";
import {
  applyContinue,
  applyEvent,
  EMPTY_PROGRESS,
  type ProgressKind,
  type ProgressStatus,
  type WorkflowProgress,
} from "@/lib/workflow-progress";
import { Button } from "@/components/ui/button";

interface Props {
  workflowId: string;
  draftVersionId?: string;
}

const KIND_ICON: Record<ProgressKind, typeof Bot> = {
  step: Bot,
  parallel: Split,
  condition: GitBranch,
  loop: Repeat,
};

const STATUS_ICON: Record<ProgressStatus, React.ReactNode> = {
  running: <Loader2 className="text-accent h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden />,
  done: (
    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-600 dark:text-green-500" aria-hidden />
  ),
  error: <XCircle className="text-destructive h-3.5 w-3.5 shrink-0" aria-hidden />,
  blocked: <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />,
};

const STATUS_LABEL: Record<ProgressStatus, string> = {
  running: "rodando",
  done: "concluída",
  error: "falhou",
  blocked: "bloqueada",
};

export function WorkflowTestPanel({ workflowId, draftVersionId }: Props) {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState<WorkflowProgress>(EMPTY_PROGRESS);
  const [input, setInput] = useState("");
  const [message, setMessage] = useState("");
  const [useDraft, setUseDraft] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const running = progress.status === "running";
  const [feedback, setFeedback] = useState("");
  const [deciding, setDeciding] = useState(false);

  async function decide(decision: StepDecision) {
    if (!progress.runId) return;
    setDeciding(true);
    setFailure(null);
    try {
      const output = await decideWorkflowStep(
        workflowId,
        progress.runId,
        progress.sessionId,
        decision,
      );
      setFeedback("");
      setProgress((p) => applyContinue(p, output));
    } catch (e) {
      setFailure(e instanceof Error ? e.message : "Falha ao registrar a decisão.");
    } finally {
      setDeciding(false);
      void queryClient.invalidateQueries({ queryKey: ["runs", workflowId] });
      void queryClient.invalidateQueries({ queryKey: ["approvals"] });
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || running || progress.status === "paused") return;
    setInput("");
    setMessage(text);
    setFailure(null);
    // cada mensagem é um run novo; a sessão segue para o histórico do workflow
    const sessionId = progress.sessionId;
    let state: WorkflowProgress = { ...EMPTY_PROGRESS, status: "running", sessionId };
    setProgress(state);

    const form = new FormData();
    form.append("message", text);
    form.append("stream", "true");
    if (sessionId) form.append("session_id", sessionId);
    if (useDraft && draftVersionId) {
      form.append("factory_input", JSON.stringify({ version_id: draftVersionId }));
    }
    try {
      const res = await fetch(`/api/workflows/${workflowId}/runs`, { method: "POST", body: form });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
      for await (const ev of readSse(res.body)) {
        state = applyEvent(state, ev);
        setProgress(state);
      }
      // stream que fecha sem WorkflowCompleted nem WorkflowError
      if (state.status === "running") setProgress({ ...state, status: "done" });
    } catch {
      setFailure("Erro ao executar o workflow.");
      setProgress((p) => ({ ...p, status: "error" }));
    } finally {
      void queryClient.invalidateQueries({ queryKey: ["runs", workflowId] });
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-foreground text-[13px] font-medium">Modo teste</h2>
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

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void send()}
          placeholder="Mensagem de entrada do workflow…"
          aria-label="Mensagem para o workflow"
          disabled={running}
          className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent flex-1 rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] transition-colors focus:outline-none disabled:opacity-40"
        />
        <Button onClick={() => void send()} disabled={running || !input.trim()} variant="strong">
          {running ? "…" : "Rodar"}
        </Button>
      </div>

      {message && (
        <p className="text-muted-foreground text-[12px]">
          Entrada: <span className="text-foreground">{message}</span>
        </p>
      )}

      {progress.steps.length > 0 && (
        <ol aria-label="Progresso das etapas" aria-busy={running} className="flex flex-col gap-1">
          {progress.steps.map((s) => {
            const Icon = KIND_ICON[s.kind];
            return (
              <li
                key={s.id}
                aria-label={`${s.name}: ${STATUS_LABEL[s.status]}`}
                className="border-border bg-card flex flex-col gap-0.5 rounded border px-2.5 py-1.5"
                style={{ marginLeft: `${s.depth * 12}px` }}
              >
                <div className="flex items-center gap-1.5 text-[12px]">
                  {STATUS_ICON[s.status]}
                  <Icon className="text-muted-foreground h-3 w-3 shrink-0" aria-hidden />
                  <span className="text-foreground font-medium">{s.name}</span>
                  {s.who && <span className="text-muted-foreground truncate">· {s.who}</span>}
                </div>
                {s.detail && (
                  <span
                    className={`text-[11px] ${
                      s.status === "error"
                        ? "text-destructive"
                        : s.status === "blocked"
                          ? "text-amber-400"
                          : "text-muted-foreground"
                    }`}
                  >
                    {s.status === "blocked" ? `bloqueada · ${blockLabel(s.detail)}` : s.detail}
                  </span>
                )}
                {s.output && (
                  <p
                    title={s.output}
                    className="text-muted-foreground line-clamp-2 text-[11px] whitespace-pre-wrap"
                  >
                    {s.output}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {progress.status === "paused" && progress.pending && (
        <div
          role="group"
          aria-label="Revisão humana"
          className="flex flex-col gap-1.5 rounded border border-amber-500/50 p-2.5 text-[12px]"
        >
          <p className="text-foreground">
            <strong>{progress.pending.stepName}</strong>
            {progress.pending.when === "after"
              ? " terminou e espera aprovação da saída."
              : " espera confirmação para rodar."}
          </p>
          {progress.pending.message && (
            <p className="text-muted-foreground">{progress.pending.message}</p>
          )}
          {progress.pending.output && (
            <pre className="border-border bg-muted text-foreground max-h-48 overflow-auto rounded border p-2 whitespace-pre-wrap">
              {progress.pending.output}
            </pre>
          )}
          <textarea
            aria-label="Motivo da recusa no teste"
            value={feedback}
            rows={2}
            placeholder="Motivo da recusa (opcional)"
            onChange={(e) => setFeedback(e.target.value)}
            className="border-border text-foreground placeholder:text-muted-foreground focus:border-accent rounded border bg-[var(--input)] px-2 py-1 focus:outline-none"
          />
          <div className="flex gap-2">
            <Button
              size="xs"
              variant="strong"
              disabled={deciding}
              onClick={() => void decide({ approve: true })}
            >
              Aprovar
            </Button>
            <Button
              size="xs"
              variant="destructive"
              disabled={deciding}
              onClick={() => void decide({ approve: false, feedback })}
            >
              Recusar
            </Button>
          </div>
        </div>
      )}

      {progress.status === "done" && progress.final && (
        <div className="flex flex-col gap-0.5" role="status">
          <span className="text-muted-foreground text-[11px]">Resposta final</span>
          <div className="border-border bg-background text-foreground rounded border px-3 py-1.5 text-[13px] whitespace-pre-wrap">
            {progress.final}
          </div>
        </div>
      )}

      {(progress.error || failure) && (
        <p className="text-destructive text-[13px]" role="alert">
          {progress.error ?? failure}
        </p>
      )}
    </div>
  );
}
