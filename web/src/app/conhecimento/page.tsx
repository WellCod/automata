"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { type EmbedderInfo, useEmbedders, useKnowledgeBases } from "@/lib/api/knowledge";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

function slugify(name: string): string {
  const s = name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 31);
  if (!s) return "";
  return /^[a-z]/.test(s) ? s : `kb_${s}`.slice(0, 31);
}

function NewBaseForm({ embedders, onDone }: { embedders: EmbedderInfo[]; onDone: () => void }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const fallback =
    embedders.find((e) => e.default && e.configured) ?? embedders.find((e) => e.configured);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [description, setDescription] = useState("");
  const [embedder, setEmbedder] = useState(fallback?.name ?? "voyage");

  const create = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/knowledge-bases", {
        body: {
          name,
          slug: slugTouched ? slug : slugify(name),
          description,
          chunk_size: 2000,
          embedder: embedder as EmbedderInfo["name"],
        },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao criar a base"));
      return res.data!;
    },
    onSuccess: (base) => {
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      onDone();
      router.push(`/conhecimento/${base.id}`);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
      className="border-border bg-card flex flex-col gap-4 rounded border p-4"
      aria-label="Nova base"
    >
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="kb-name">Nome</FieldLabel>
          <input
            id="kb-name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="kb-slug">Identificador</FieldLabel>
          <input
            id="kb-slug"
            value={slugTouched ? slug : slugify(name)}
            onChange={(e) => {
              setSlugTouched(true);
              setSlug(e.target.value);
            }}
            className={inputCls}
          />
          <FieldDescription>
            Vira o nome da busca do agente (<code>buscar_{slugTouched ? slug : slugify(name)}</code>
            ) e não muda depois.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="kb-description">Descrição</FieldLabel>
          <textarea
            id="kb-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className={`${inputCls} resize-y`}
            placeholder="Ex.: políticas de RH — férias, benefícios e reembolso"
          />
          <FieldDescription>
            O agente lê a descrição para decidir quando buscar aqui.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="kb-embedder">Embedder</FieldLabel>
          <select
            id="kb-embedder"
            value={embedder}
            onChange={(e) => setEmbedder(e.target.value as EmbedderInfo["name"])}
            className={inputCls}
          >
            {embedders.map((e) => (
              <option key={e.name} value={e.name} disabled={!e.configured}>
                {e.name} · {e.model}
                {e.configured ? "" : " (sem chave na API)"}
              </option>
            ))}
          </select>
          <FieldDescription>Fixo depois de criada: trocar exige recriar a base.</FieldDescription>
        </Field>
      </FieldGroup>
      {create.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {create.error.message}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="muted" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" variant="strong" disabled={create.isPending || !name || !fallback}>
          {create.isPending ? "Criando…" : "Criar base"}
        </Button>
      </div>
    </form>
  );
}

export default function KnowledgeBasesPage() {
  const { data: bases, isPending, isError } = useKnowledgeBases();
  const { data: embedders } = useEmbedders();
  const [creating, setCreating] = useState(false);
  const noKey = embedders && !embedders.some((e) => e.configured);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <h1 className="text-foreground text-sm font-medium">Conhecimento</h1>
        <Button variant="accent" onClick={() => setCreating(true)} disabled={creating}>
          Nova base
        </Button>
      </header>

      <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-6">
        <p className="text-muted-foreground text-[13px]">
          Documentos que os agentes consultam antes de responder. Uma base pode servir vários
          agentes; o conteúdo vale na hora para todos que a usam.
        </p>

        {noKey && (
          <p
            className="rounded border border-amber-400/40 px-3 py-2 text-[13px] text-amber-600 dark:text-amber-400"
            role="alert"
          >
            Nenhum embedder com chave na API. Defina <code>VOYAGE_API_KEY</code> ou{" "}
            <code>OPENAI_API_KEY</code> para criar bases.
          </p>
        )}

        {creating && embedders && (
          <NewBaseForm embedders={embedders} onDone={() => setCreating(false)} />
        )}

        {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive text-[13px]" role="alert">
            Não foi possível carregar as bases.
          </p>
        )}
        {bases && bases.length === 0 && !creating && (
          <div className="border-border flex flex-col items-center gap-3 rounded border border-dashed px-6 py-10 text-center">
            <BookOpen className="text-accent h-5 w-5" aria-hidden />
            <p className="text-foreground text-sm">Nenhuma base de conhecimento</p>
            <p className="text-muted-foreground max-w-md text-[13px]">
              Crie uma base, envie PDFs, documentos ou páginas, e ligue a base aos agentes que devem
              consultá-la.
            </p>
          </div>
        )}
        {bases && bases.length > 0 && (
          <ul className="flex flex-col gap-2">
            {bases.map((base) => (
              <li key={base.id}>
                <Link
                  href={`/conhecimento/${base.id}`}
                  className="border-border bg-card hover:border-accent/60 flex flex-col gap-1 rounded border px-4 py-3 transition-colors"
                >
                  <span className="text-foreground text-sm font-medium">{base.name}</span>
                  {base.description && (
                    <span className="text-muted-foreground text-[13px]">{base.description}</span>
                  )}
                  <span className="text-muted-foreground text-[11px]">
                    <code>buscar_{base.slug}</code> · {base.embedder_model}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
