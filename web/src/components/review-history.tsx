"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";
import { TextDiff } from "@/components/step-review-actions";

type ReviewEntry = components["schemas"]["ReviewEntry"];

export const DECISION_LABEL: Record<string, string> = {
  approved: "aprovou",
  rejected: "recusou",
  edited: "editou e aprovou",
  loop_done: "seguiu com a volta",
  loop_again: "pediu outra volta",
  timeout: "venceu sem decisão e cancelou o workflow",
};

function when(iso: string): string {
  return new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

function Entry({ entry }: { entry: ReviewEntry }) {
  const [open, setOpen] = useState(false);
  const edited = entry.decision === "edited";
  return (
    <li className="flex flex-col gap-1 text-[12px]">
      <span className="text-foreground">
        <strong>{entry.by}</strong> {DECISION_LABEL[entry.decision] ?? entry.decision}{" "}
        <strong>{entry.step_name}</strong>
        <span className="text-muted-foreground"> · {when(entry.at)}</span>
      </span>
      {entry.feedback && <span className="text-muted-foreground">“{entry.feedback}”</span>}
      {edited && (
        <>
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="text-accent w-fit text-[12px] underline"
          >
            {open ? "Esconder a edição" : "Ver a edição"}
          </button>
          {open && <TextDiff before={entry.before ?? ""} after={entry.after ?? ""} />}
        </>
      )}
    </li>
  );
}

/** Quem decidiu cada pausa do run do workflow (ADR-0028); some quando não houve decisão. */
export function ReviewHistory({ runId }: { runId: string }) {
  const { data } = useQuery({
    queryKey: ["run-reviews", runId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/runs/{run_id}/reviews", {
        params: { path: { run_id: runId } },
      });
      // run de agente, ou de outro usuário: sem histórico para mostrar
      if (res.error) return [];
      return res.data ?? [];
    },
  });
  if (!data || data.length === 0) return null;
  return (
    <section aria-label="Decisões humanas" className="flex flex-col gap-1.5">
      <h3 className="text-muted-foreground text-[11px] font-medium">Decisões humanas</h3>
      <ol className="flex flex-col gap-1.5">
        {data.map((e, i) => (
          <Entry key={`${e.step_id}-${i}`} entry={e} />
        ))}
      </ol>
    </section>
  );
}
