"use client";

import { useId, useState } from "react";
import type { StepDecision } from "@/lib/api/approvals";
import { diffLines } from "@/lib/text-diff";
import { Button } from "@/components/ui/button";

// mesmo teto do registro na API (app/agents/reviews.py)
export const MAX_EDITED_CHARS = 20_000;

const inputCls =
  "border-border text-foreground placeholder:text-muted-foreground focus:border-accent rounded border bg-[var(--input)] px-3 py-1.5 text-[13px] focus:outline-none";

export function TextDiff({ before, after }: { before: string; after: string }) {
  const lines = diffLines(before, after);
  if (lines === null)
    return <p className="text-muted-foreground text-[12px]">Texto longo demais para o diff.</p>;
  return (
    <pre
      aria-label="Diferença da edição"
      className="border-border bg-muted max-h-48 overflow-auto rounded border p-2 text-[12px] whitespace-pre-wrap"
    >
      {lines.map((l, i) => (
        <div
          key={i}
          className={
            l.kind === "added"
              ? "text-emerald-700 dark:text-emerald-400"
              : l.kind === "removed"
                ? "text-destructive line-through"
                : "text-muted-foreground"
          }
        >
          {l.kind === "added" ? "+ " : l.kind === "removed" ? "− " : "  "}
          {l.text}
        </div>
      ))}
    </pre>
  );
}

/**
 * Decisão sobre a pausa do workflow (ADR-0023, ADR-0028): a mesma na página Aprovações
 * e no modo teste. A volta de laço só segue ou pede outra; a saída pronta pode ser editada.
 */
export function StepReviewActions({
  when,
  output,
  busy,
  onDecide,
  size = "default",
}: {
  when: "before" | "after" | "loop";
  output?: string | null;
  busy: boolean;
  onDecide: (decision: StepDecision) => void;
  size?: "default" | "xs";
}) {
  const id = useId();
  const [feedback, setFeedback] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [editing, setEditing] = useState(false);
  const [edited, setEdited] = useState(output ?? "");
  const changed = editing && edited.trim() !== "" && edited !== (output ?? "");

  function decide(decision: StepDecision) {
    onDecide(decision);
    setFeedback("");
    setEditing(false);
  }

  if (when === "loop")
    return (
      <div className="flex flex-col gap-2">
        <textarea
          aria-label="Comentário para a próxima volta"
          value={feedback}
          rows={2}
          maxLength={1000}
          placeholder="O que mudar na próxima volta"
          onChange={(e) => setFeedback(e.target.value)}
          className={inputCls}
        />
        <div className="flex flex-wrap gap-2">
          <Button
            size={size}
            variant="strong"
            disabled={busy}
            onClick={() => decide({ approve: true })}
          >
            Seguir com esta volta
          </Button>
          <Button
            size={size}
            variant="muted"
            disabled={busy || !feedback.trim()}
            onClick={() => decide({ approve: false, feedback })}
          >
            Pedir outra volta
          </Button>
        </div>
      </div>
    );

  return (
    <div className="flex flex-col gap-2">
      {editing ? (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={id} className="text-foreground text-[12px]">
            Saída editada (segue para a próxima etapa no lugar da original)
          </label>
          <textarea
            id={id}
            value={edited}
            rows={6}
            maxLength={MAX_EDITED_CHARS}
            onChange={(e) => setEdited(e.target.value)}
            className={`${inputCls} font-mono text-[12px]`}
          />
          {changed && <TextDiff before={output ?? ""} after={edited} />}
        </div>
      ) : (
        <textarea
          aria-label="Motivo da recusa"
          value={feedback}
          rows={2}
          maxLength={1000}
          placeholder="Motivo da recusa (opcional; vai para a etapa quando ela é refeita)"
          onChange={(e) => setFeedback(e.target.value)}
          className={inputCls}
        />
      )}
      <div className="flex flex-wrap gap-2">
        {editing ? (
          <>
            <Button
              size={size}
              variant="strong"
              disabled={busy || !changed}
              onClick={() => decide({ approve: true, edited })}
            >
              Aprovar com a edição
            </Button>
            <Button size={size} variant="muted" disabled={busy} onClick={() => setEditing(false)}>
              Descartar edição
            </Button>
          </>
        ) : (
          <>
            <Button
              size={size}
              variant="strong"
              disabled={busy}
              onClick={() => decide({ approve: true })}
            >
              Aprovar
            </Button>
            {when === "after" && output != null && (
              <Button
                size={size}
                variant="muted"
                disabled={busy}
                onClick={() => {
                  setEdited(output);
                  setEditing(true);
                }}
              >
                Editar saída
              </Button>
            )}
            {/* recusar encerra, pula ou refaz a etapa: pede confirmação (Fase 44) */}
            {confirming ? (
              <>
                <Button
                  size={size}
                  variant="destructive"
                  disabled={busy}
                  onClick={() => decide({ approve: false, feedback })}
                >
                  Confirmar recusa
                </Button>
                <Button
                  size={size}
                  variant="muted"
                  disabled={busy}
                  onClick={() => setConfirming(false)}
                >
                  Voltar
                </Button>
              </>
            ) : (
              <Button
                size={size}
                variant="subtleDestructive"
                disabled={busy}
                onClick={() => setConfirming(true)}
              >
                Recusar
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
