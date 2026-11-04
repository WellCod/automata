"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";

export const MAX_FIELDS = 10;
const FIELD_NAME = /^[a-z0-9_]{1,40}$/;

export type Fields = Record<string, string>;

/** "plano=a, ano=2026" ou uma linha por campo; mesmas regras de check_fields na API (ADR-0033). */
export function parseFields(text: string): { fields: Fields; problems: string[] } {
  const fields: Fields = {};
  const problems: string[] = [];
  for (const raw of text.split(/[\n,]/)) {
    const part = raw.trim();
    if (!part) continue;
    const eq = part.indexOf("=");
    if (eq < 1) {
      problems.push(`"${part}": use campo=valor.`);
      continue;
    }
    const name = part.slice(0, eq).trim();
    const value = part.slice(eq + 1).trim();
    if (!FIELD_NAME.test(name)) {
      problems.push(`"${name}": minúsculas, dígitos e _, até 40.`);
      continue;
    }
    if (value.length < 1 || value.length > 100) {
      problems.push(`"${name}": o valor precisa ter de 1 a 100 caracteres.`);
      continue;
    }
    fields[name] = value;
  }
  if (Object.keys(fields).length > MAX_FIELDS)
    problems.push(`No máximo ${MAX_FIELDS} campos por documento.`);
  return { fields, problems };
}

export function formatFields(fields: Fields | null | undefined): string {
  return Object.entries(fields ?? {})
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}

export function FieldChips({ fields }: { fields: Fields | null | undefined }) {
  const entries = Object.entries(fields ?? {});
  if (entries.length === 0) return null;
  return (
    <ul aria-label="Campos do documento" className="flex flex-wrap gap-1">
      {entries.map(([k, v]) => (
        <li
          key={k}
          className="border-border text-muted-foreground rounded border px-1.5 py-0.5 text-[11px]"
        >
          {k}: <span className="text-foreground">{v}</span>
        </li>
      ))}
    </ul>
  );
}

/** Edita os campos de um documento; a API troca os campos nos trechos sem embedar de novo. */
export function DocumentFieldsEditor({
  baseId,
  contentId,
  name,
  fields,
  onClose,
}: {
  baseId: string;
  contentId: string;
  name: string;
  fields: Fields | null | undefined;
  onClose: () => void;
}) {
  const id = useId();
  const queryClient = useQueryClient();
  const [text, setText] = useState(formatFields(fields));
  const { fields: parsed, problems } = parseFields(text);
  const save = useMutation({
    mutationFn: async () => {
      const res = await client.PUT(
        "/api/v1/knowledge-bases/{base_id}/contents/{content_id}/fields",
        {
          params: { path: { base_id: baseId, content_id: contentId } },
          body: { fields: Object.keys(parsed).length ? parsed : null },
        },
      );
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar os campos"));
    },
    onSuccess: () => {
      toast.success(`Campos de ${name} salvos`);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId] });
      onClose();
    },
    onError: (e) => toast.error(e.message),
  });
  return (
    <div role="group" aria-label={`Campos de ${name}`} className="flex flex-col gap-1.5 pt-1">
      <label htmlFor={`${id}-fields`} className="text-muted-foreground text-[11px]">
        Um campo por linha, como produto=plano a. O agente pode filtrar a busca por eles.
      </label>
      <textarea
        id={`${id}-fields`}
        rows={3}
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="border-border text-foreground w-full rounded border bg-[var(--input)] px-2 py-1 font-mono text-[12px] focus:outline-none"
      />
      {problems.map((p) => (
        <p key={p} className="text-destructive text-[11px]">
          {p}
        </p>
      ))}
      <div className="flex gap-2">
        <Button
          size="xs"
          variant="strong"
          disabled={problems.length > 0 || save.isPending}
          onClick={() => save.mutate()}
        >
          Salvar campos
        </Button>
        <Button size="xs" variant="muted" onClick={onClose}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
