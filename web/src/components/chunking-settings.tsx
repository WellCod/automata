"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";

export type ChunkingSettings = components["schemas"]["ChunkingSettings"];
type ChunkPreview = components["schemas"]["ChunkPreview"];
type ReprocessResult = components["schemas"]["ReprocessResult"];

export const DEFAULT_CHUNKING: ChunkingSettings = {
  strategy: "recursive",
  overlap: null,
  heading_level: 2,
};

// mesma regra de overlap_problem na API (ADR-0029)
export const MAX_OVERLAP_RATIO = 0.3;

export function overlapProblem(chunkSize: number, chunking: ChunkingSettings): string | null {
  if (chunking.overlap == null) return null;
  if (chunking.overlap > chunkSize * MAX_OVERLAP_RATIO)
    return `A sobreposição passa de 30% do tamanho do trecho (${Math.floor(chunkSize * MAX_OVERLAP_RATIO)} caracteres).`;
  return null;
}

const STRATEGIES: { value: ChunkingSettings["strategy"]; label: string; hint: string }[] = [
  {
    value: "recursive",
    label: "Recursivo",
    hint: "Corta no fim de linha ou de frase mais perto do tamanho. Serve para quase tudo.",
  },
  {
    value: "headings",
    label: "Por títulos",
    hint: "Um trecho por seção de markdown (#, ##, ###), com o título no início. Bom para manuais e FAQs.",
  },
  {
    value: "paragraphs",
    label: "Por parágrafos",
    hint: "Junta parágrafos inteiros até o tamanho, sem cortar um parágrafo ao meio.",
  },
  {
    value: "fixed",
    label: "Tamanho fixo",
    hint: "Corta a cada N caracteres, sem olhar a estrutura. Útil para texto corrido sem pontuação.",
  },
];

const inputCls =
  "rounded border border-border bg-[var(--input)] px-2 py-1 text-[13px] text-foreground focus:border-accent focus:outline-none";

export function ChunkingFields({
  value,
  onChange,
  chunkSize,
}: {
  value: ChunkingSettings;
  onChange: (v: ChunkingSettings) => void;
  chunkSize: number;
}) {
  const current = STRATEGIES.find((s) => s.value === value.strategy);
  const problem = overlapProblem(chunkSize, value);
  return (
    <div className="flex flex-col gap-2">
      <label className="text-foreground flex flex-wrap items-center gap-2 text-[13px]">
        Estratégia de corte
        <select
          aria-label="Estratégia de corte"
          value={value.strategy}
          onChange={(e) =>
            onChange({ ...value, strategy: e.target.value as ChunkingSettings["strategy"] })
          }
          className={inputCls}
        >
          {STRATEGIES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {value.strategy === "headings" && (
          <select
            aria-label="Nível de título"
            value={value.heading_level ?? 2}
            onChange={(e) => onChange({ ...value, heading_level: Number(e.target.value) })}
            className={inputCls}
          >
            <option value={1}>até #</option>
            <option value={2}>até ##</option>
            <option value={3}>até ###</option>
          </select>
        )}
      </label>
      {current && <p className="text-muted-foreground text-[12px]">{current.hint}</p>}
      <label className="text-foreground flex flex-wrap items-center gap-2 text-[13px]">
        Sobreposição entre trechos
        <input
          type="number"
          aria-label="Sobreposição entre trechos"
          min={0}
          max={Math.floor(chunkSize * MAX_OVERLAP_RATIO)}
          placeholder={`padrão: ${Math.floor(chunkSize / 10)}`}
          value={value.overlap ?? ""}
          onChange={(e) =>
            onChange({ ...value, overlap: e.target.value === "" ? null : Number(e.target.value) })
          }
          className={`${inputCls} w-28`}
        />
        caracteres
      </label>
      {problem ? (
        <p className="text-destructive text-[12px]" role="alert">
          {problem}
        </p>
      ) : (
        <p className="text-muted-foreground text-[12px]">
          Repete o fim de um trecho no começo do seguinte, para a frase cortada não se perder. Vazio
          usa 10% do tamanho do trecho.
        </p>
      )}
    </div>
  );
}

/** Trechos que um texto daria com o corte da tela, sem gravar nem cobrar (ADR-0029). */
export function ChunkPreviewPanel({
  baseId,
  chunkSize,
  chunking,
}: {
  baseId: string;
  chunkSize: number;
  chunking: ChunkingSettings;
}) {
  const [text, setText] = useState("");
  const preview = useMutation({
    mutationFn: async (): Promise<ChunkPreview> => {
      const res = await client.POST("/api/v1/knowledge-bases/{base_id}/chunk-preview", {
        params: { path: { base_id: baseId } },
        body: { text, chunk_size: chunkSize, chunking },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha na prévia"));
      return res.data;
    },
  });
  const blocked = overlapProblem(chunkSize, chunking) !== null;
  return (
    <section aria-label="Prévia dos trechos" className="flex flex-col gap-2">
      <textarea
        aria-label="Texto para a prévia"
        value={text}
        maxLength={50_000}
        rows={5}
        placeholder="Cole um pedaço de um documento desta base para ver como ele seria cortado"
        onChange={(e) => setText(e.target.value)}
        className={`${inputCls} w-full resize-y font-mono text-[12px]`}
      />
      <div className="flex items-center gap-2">
        <Button
          variant="muted"
          disabled={!text.trim() || blocked || preview.isPending}
          onClick={() => preview.mutate()}
        >
          {preview.isPending ? "Cortando…" : "Ver trechos"}
        </Button>
        <span className="text-muted-foreground text-[12px]">Sem custo: nada é embedado.</span>
      </div>
      {preview.isError && (
        <p className="text-destructive text-[12px]" role="alert">
          {preview.error.message}
        </p>
      )}
      {preview.data && (
        <div className="flex flex-col gap-1.5">
          <p className="text-foreground text-[12px]">
            {preview.data.total} trecho{preview.data.total === 1 ? "" : "s"}
            {preview.data.total > preview.data.chunks.length
              ? ` (mostrando os ${preview.data.chunks.length} primeiros)`
              : ""}
          </p>
          <ol className="flex flex-col gap-1.5">
            {preview.data.chunks.map((chunk, i) => (
              <li
                key={i}
                className="border-border bg-muted rounded border px-2 py-1.5 text-[12px] whitespace-pre-wrap"
              >
                <span className="text-muted-foreground block text-[11px]">
                  Trecho {i + 1} · {chunk.length} caracteres
                </span>
                {chunk}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}

/** Reindexa a base com o corte salvo; o embedding é cobrado de novo. */
export function ReprocessBase({ baseId, dirty }: { baseId: string; dirty: boolean }) {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const run = useMutation({
    mutationFn: async (): Promise<ReprocessResult> => {
      const res = await client.POST("/api/v1/knowledge-bases/{base_id}/reprocess", {
        params: { path: { base_id: baseId } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao reprocessar"));
      return res.data;
    },
    onSuccess: (result) => {
      setConfirm(false);
      if (result.queued === 0) toast.info("Nada que a base consiga reler sozinha");
      else
        toast.success(
          `${result.queued} conteúdo${result.queued === 1 ? "" : "s"} em reprocessamento`,
        );
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "contents"] });
    },
    onError: (e) => toast.error(e.message),
  });
  const result = run.data;
  return (
    <section aria-label="Reprocessar a base" className="flex flex-col gap-2">
      {confirm ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-amber-600 dark:text-amber-400">
            Todo o conteúdo volta a ser indexado e o embedding é cobrado de novo. Enquanto isso, ele
            some da busca.
          </span>
          <Button variant="strong" disabled={run.isPending} onClick={() => run.mutate()}>
            {run.isPending ? "Enviando…" : "Confirmar reprocessamento"}
          </Button>
          <Button variant="muted" onClick={() => setConfirm(false)}>
            Cancelar
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="muted" disabled={dirty} onClick={() => setConfirm(true)}>
            Reprocessar a base
          </Button>
          <span className="text-muted-foreground text-[12px]">
            {dirty
              ? "Salve antes: o reprocessamento usa o corte gravado."
              : "Aplica o corte salvo ao que já está na base."}
          </span>
        </div>
      )}
      {result && result.needs_upload.length > 0 && (
        <div className="text-[12px]" role="status">
          <p className="text-foreground">
            Enviados antes do corte por base, sem o original guardado. Envie de novo para usar o
            corte novo:
          </p>
          <ul className="text-muted-foreground list-disc pl-5">
            {result.needs_upload.map((c) => (
              <li key={c.id}>{c.name}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
