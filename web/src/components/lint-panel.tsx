"use client";

import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle } from "lucide-react";
import client from "@/lib/api/client";
import type { components } from "@/lib/api/schema.d.ts";

type ConfigPayload = components["schemas"]["ConfigPayload"];
type LintWarning = components["schemas"]["LintWarning"];

interface Props {
  getPayload: () => ConfigPayload | null;
}

export function LintPanel({ getPayload }: Props) {
  const mutation = useMutation({
    mutationFn: async () => {
      const payload = getPayload();
      if (!payload) throw new Error("Sem payload para verificar");
      const res = await client.POST("/api/v1/linter", { body: payload });
      if (res.error) throw new Error("Falha ao executar linter");
      return res.data!;
    },
  });

  const warnings: LintWarning[] = mutation.data ?? [];

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-foreground text-[13px] font-medium">Linter</h2>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="border-border text-muted-foreground hover:border-foreground/50 hover:text-foreground inline-flex h-6 items-center rounded border px-2 text-[10px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
        >
          {mutation.isPending ? "Verificando…" : "Verificar"}
        </button>
      </div>

      {mutation.isSuccess && (
        <div>
          {warnings.length === 0 ? (
            <div className="text-accent flex items-center gap-1.5 text-[13px]">
              <CheckCircle className="h-3.5 w-3.5" />
              Sem avisos
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {warnings.map((w, i) => (
                <li
                  key={i}
                  className="border-border bg-card flex items-start gap-2 rounded border px-3 py-2 text-[13px]"
                >
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
                  <div>
                    <span className="text-foreground font-medium">{w.section}</span>
                    <span className="text-muted-foreground mx-1">·</span>
                    <span className="text-muted-foreground font-mono">{w.code}</span>
                    <p className="text-muted-foreground mt-0.5">{w.message}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mutation.isError && <p className="text-destructive text-[13px]">Erro ao executar linter.</p>}
    </div>
  );
}
