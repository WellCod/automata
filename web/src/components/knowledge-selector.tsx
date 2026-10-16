"use client";

import Link from "next/link";
import { useId } from "react";
import { type KnowledgeBase, useKnowledgeBases } from "@/lib/api/knowledge";

export type KnowledgeBinding = { base_id: string; max_results: number };

interface Props {
  value: KnowledgeBinding[];
  onChange: (value: KnowledgeBinding[]) => void;
}

function BaseRow({
  base,
  binding,
  onChange,
}: {
  base: KnowledgeBase;
  binding: KnowledgeBinding | undefined;
  onChange: (binding: KnowledgeBinding | undefined) => void;
}) {
  const id = useId();
  return (
    <div className="border-border flex items-start justify-between gap-3 rounded border px-3 py-2.5">
      <label htmlFor={`${id}-use`} className="flex min-w-0 items-start gap-2">
        <input
          id={`${id}-use`}
          type="checkbox"
          checked={binding !== undefined}
          onChange={(e) =>
            onChange(e.target.checked ? { base_id: base.id, max_results: 5 } : undefined)
          }
          className="mt-0.5 h-3.5 w-3.5 accent-[var(--accent)]"
        />
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-foreground text-[13px]">{base.name}</span>
          {base.description && (
            <span className="text-muted-foreground text-[11px]">{base.description}</span>
          )}
          <code className="text-muted-foreground text-[11px]">buscar_{base.slug}</code>
        </span>
      </label>
      {binding && (
        <label htmlFor={`${id}-max`} className="flex flex-none items-center gap-1.5">
          <span className="text-muted-foreground text-[11px]">trechos</span>
          <input
            id={`${id}-max`}
            type="number"
            min={1}
            max={20}
            value={binding.max_results}
            onChange={(e) =>
              onChange({
                ...binding,
                max_results: Math.min(20, Math.max(1, Number(e.target.value) || 1)),
              })
            }
            aria-label={`Trechos por busca em ${base.name}`}
            className="border-border text-foreground focus:border-accent w-14 rounded border bg-[var(--input)] px-2 py-1 text-[13px] focus:outline-none"
          />
        </label>
      )}
    </div>
  );
}

export function KnowledgeSelector({ value, onChange }: Props) {
  const { data: bases, isPending, isError } = useKnowledgeBases();
  const byId = new Map(value.map((b) => [b.base_id, b]));
  // ligação a base removida some da lista, mas segue no valor até salvar
  const missing = value.filter((b) => bases && !bases.some((base) => base.id === b.base_id));

  function set(baseId: string, binding: KnowledgeBinding | undefined) {
    const rest = value.filter((b) => b.base_id !== baseId);
    onChange(binding ? [...rest, binding] : rest);
  }

  return (
    <fieldset className="border-border flex flex-col gap-2 rounded border px-4 pt-3 pb-4">
      <legend className="text-foreground px-1 text-[13px] font-medium">
        Bases de conhecimento
      </legend>
      <p className="text-muted-foreground text-[11px]">
        O agente ganha uma busca por base e consulta antes de responder sobre os temas dela.{" "}
        <Link href="/conhecimento" className="text-accent hover:underline">
          Gerenciar bases
        </Link>
      </p>
      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar as bases.
        </p>
      )}
      {bases && bases.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhuma base cadastrada.</p>
      )}
      {bases?.map((base) => (
        <BaseRow
          key={base.id}
          base={base}
          binding={byId.get(base.id)}
          onChange={(b) => set(base.id, b)}
        />
      ))}
      {missing.length > 0 && (
        <p className="text-destructive text-[11px]" role="alert">
          {missing.length} base(s) ligada(s) não existem mais.{" "}
          <button
            type="button"
            className="underline"
            onClick={() => onChange(value.filter((b) => !missing.includes(b)))}
          >
            Remover
          </button>
        </p>
      )}
    </fieldset>
  );
}
