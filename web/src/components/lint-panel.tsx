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
    <div className="rounded-lg border border-zinc-200 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-zinc-700">Linter</h2>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="rounded-md border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-50"
        >
          {mutation.isPending ? "Verificando…" : "Verificar"}
        </button>
      </div>

      {mutation.isSuccess && (
        <div className="mt-3">
          {warnings.length === 0 ? (
            <div className="flex items-center gap-1.5 text-xs text-green-600">
              <CheckCircle className="h-3.5 w-3.5" />
              Sem avisos
            </div>
          ) : (
            <ul className="flex flex-col gap-2">
              {warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-xs">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                  <div>
                    <span className="font-medium text-zinc-700">{w.section}</span>
                    <span className="mx-1 text-zinc-400">·</span>
                    <span className="font-mono text-zinc-500">{w.code}</span>
                    <p className="mt-0.5 text-zinc-600">{w.message}</p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {mutation.isError && <p className="mt-3 text-xs text-red-500">Erro ao executar linter.</p>}
    </div>
  );
}
