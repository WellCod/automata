"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileText, Search, Settings2, Upload } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import {
  type KnowledgeBase,
  type KnowledgeContent,
  type SearchHit,
  uploadFile,
  useKnowledgeBase,
  useKnowledgeContents,
} from "@/lib/api/knowledge";
import { cn } from "@/lib/utils";

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

const ACCEPT = ".pdf,.docx,.md,.txt,.csv,.json";

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function StatusBadge({ content }: { content: KnowledgeContent }) {
  if (content.status === "processing") {
    return <span className="text-[11px] text-amber-400">processando…</span>;
  }
  if (content.status === "failed") {
    return <span className="text-destructive text-[11px]">falhou</span>;
  }
  return (
    <span className="text-accent text-[11px]">
      {content.chunk_count} trecho{content.chunk_count === 1 ? "" : "s"}
    </span>
  );
}

function ContentRow({ baseId, content }: { baseId: string; content: KnowledgeContent }) {
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/knowledge-bases/{base_id}/contents/{content_id}", {
        params: { path: { base_id: baseId, content_id: content.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover"));
    },
    onSuccess: () => {
      toast.success(`${content.name} removido`);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "contents"] });
    },
    onError: (e) => toast.error(e.message),
  });

  return (
    <li className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="text-muted-foreground h-3.5 w-3.5 flex-none" aria-hidden />
          <span className="text-foreground truncate text-[13px] font-medium">{content.name}</span>
          <StatusBadge content={content} />
        </div>
        <div className="flex flex-none items-center gap-2">
          <span className="text-muted-foreground text-[11px]">
            {content.source_type === "url" ? "URL" : content.extension.toUpperCase()} ·{" "}
            {formatSize(content.size_bytes)}
          </span>
          {confirm ? (
            <>
              <Button size="xs" variant="destructive" onClick={() => remove.mutate()}>
                Confirmar
              </Button>
              <Button size="xs" variant="muted" onClick={() => setConfirm(false)}>
                Manter
              </Button>
            </>
          ) : (
            <Button size="xs" variant="subtleDestructive" onClick={() => setConfirm(true)}>
              Remover
            </Button>
          )}
        </div>
      </div>
      {content.source_type === "url" && content.source !== content.name && (
        <span className="text-muted-foreground truncate text-[11px]">{content.source}</span>
      )}
      {content.status === "failed" && content.status_message && (
        <p className="text-destructive text-[11px]" role="alert">
          {content.status_message}
        </p>
      )}
    </li>
  );
}

function AddContent({ baseId }: { baseId: string }) {
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [mode, setMode] = useState<"url" | "text" | null>(null);
  const [url, setUrl] = useState("");
  const [textName, setTextName] = useState("");
  const [text, setText] = useState("");
  const refresh = () =>
    void queryClient.invalidateQueries({ queryKey: ["knowledge-bases", baseId, "contents"] });

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      // um por vez: a API processa cada arquivo numa thread, sem fila
      for (const file of files) await uploadFile(baseId, file);
      return files.length;
    },
    onSuccess: (n) => {
      toast.success(n === 1 ? "Arquivo enviado" : `${n} arquivos enviados`);
      refresh();
    },
    onError: (e) => {
      toast.error(e.message);
      refresh();
    },
  });

  const addUrl = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/knowledge-bases/{base_id}/contents/url", {
        params: { path: { base_id: baseId } },
        body: { url },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao adicionar URL"));
    },
    onSuccess: () => {
      setUrl("");
      setMode(null);
      refresh();
    },
  });

  const addText = useMutation({
    mutationFn: async () => {
      const res = await client.POST("/api/v1/knowledge-bases/{base_id}/contents/text", {
        params: { path: { base_id: baseId } },
        body: { name: textName, text },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao adicionar texto"));
    },
    onSuccess: () => {
      setTextName("");
      setText("");
      setMode(null);
      refresh();
    },
  });

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const files = Array.from(e.dataTransfer.files);
          if (files.length) upload.mutate(files);
        }}
        className={cn(
          "border-border flex flex-col items-center gap-2 rounded border border-dashed px-6 py-6 text-center transition-colors",
          dragging && "border-accent",
        )}
      >
        <Upload className="text-muted-foreground h-4 w-4" aria-hidden />
        <p className="text-muted-foreground text-[13px]">
          Arraste arquivos aqui (PDF, DOCX, Markdown, texto, CSV, JSON)
        </p>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
            {upload.isPending ? "Enviando…" : "Escolher arquivos"}
          </Button>
          <Button size="sm" variant="muted" onClick={() => setMode(mode === "url" ? null : "url")}>
            Adicionar URL
          </Button>
          <Button
            size="sm"
            variant="muted"
            onClick={() => setMode(mode === "text" ? null : "text")}
          >
            Colar texto
          </Button>
        </div>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          aria-label="Arquivos para a base"
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            if (files.length) upload.mutate(files);
            e.target.value = "";
          }}
        />
      </div>

      {mode === "url" && (
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            addUrl.mutate();
          }}
        >
          <input
            type="url"
            required
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://empresa.com/politicas"
            aria-label="URL"
            className={inputCls}
          />
          <Button type="submit" variant="strong" disabled={addUrl.isPending}>
            Adicionar
          </Button>
        </form>
      )}
      {addUrl.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {addUrl.error.message}
        </p>
      )}

      {mode === "text" && (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            addText.mutate();
          }}
        >
          <input
            required
            value={textName}
            onChange={(e) => setTextName(e.target.value)}
            placeholder="Nome do documento"
            aria-label="Nome do documento"
            className={inputCls}
          />
          <textarea
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={6}
            aria-label="Texto"
            className={`${inputCls} resize-y`}
          />
          <div className="flex justify-end">
            <Button type="submit" variant="strong" disabled={addText.isPending}>
              Adicionar texto
            </Button>
          </div>
        </form>
      )}
      {addText.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {addText.error.message}
        </p>
      )}
    </div>
  );
}

function Documents({ baseId }: { baseId: string }) {
  const { data, isPending, isError } = useKnowledgeContents(baseId);
  return (
    <div className="flex flex-col gap-4">
      <AddContent baseId={baseId} />
      {isPending && <p className="text-muted-foreground text-[13px]">Carregando…</p>}
      {isError && (
        <p className="text-destructive text-[13px]" role="alert">
          Não foi possível carregar os documentos.
        </p>
      )}
      {data && data.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nenhum documento ainda.</p>
      )}
      {data && data.length > 0 && (
        <ul className="flex flex-col gap-1">
          {data.map((c) => (
            <ContentRow key={c.id} baseId={baseId} content={c} />
          ))}
        </ul>
      )}
    </div>
  );
}

function TestSearch({ baseId }: { baseId: string }) {
  const [query, setQuery] = useState("");
  const search = useMutation({
    mutationFn: async (): Promise<SearchHit[]> => {
      const res = await client.POST("/api/v1/knowledge-bases/{base_id}/search", {
        params: { path: { base_id: baseId } },
        body: { query, max_results: 5 },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha na busca"));
      return res.data!;
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <p className="text-muted-foreground text-[13px]">
        Os trechos que o agente receberia para esta pergunta, sem rodar o agente.
      </p>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (query.trim()) search.mutate();
        }}
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Quantos dias de férias tenho por ano?"
          aria-label="Pergunta"
          className={inputCls}
        />
        <Button type="submit" variant="strong" disabled={search.isPending || !query.trim()}>
          {search.isPending ? "Buscando…" : "Buscar"}
        </Button>
      </form>
      {search.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {search.error.message}
        </p>
      )}
      {search.data && search.data.length === 0 && (
        <p className="text-muted-foreground text-[13px]">Nada encontrado.</p>
      )}
      {search.data && search.data.length > 0 && (
        <ol className="flex flex-col gap-2">
          {search.data.map((hit, i) => (
            <li
              key={i}
              className="border-border bg-card flex flex-col gap-1 rounded border px-3 py-2"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-foreground text-[13px] font-medium">
                  {hit.content_name ?? hit.source ?? "documento"}
                </span>
                {hit.score !== null && (
                  <span className="text-muted-foreground text-[11px]">
                    relevância {Math.round(hit.score * 100)}%
                  </span>
                )}
              </div>
              <p className="text-muted-foreground text-[13px] whitespace-pre-line">{hit.text}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function Settings({ base }: { base: KnowledgeBase }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [name, setName] = useState(base.name);
  const [description, setDescription] = useState(base.description);
  const [chunkSize, setChunkSize] = useState(base.chunk_size);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const save = useMutation({
    mutationFn: async () => {
      const res = await client.PUT("/api/v1/knowledge-bases/{base_id}", {
        params: { path: { base_id: base.id } },
        body: { name, description, chunk_size: chunkSize },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar"));
    },
    onSuccess: () => {
      toast.success("Base salva");
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
    },
    onError: (e) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/knowledge-bases/{base_id}", {
        params: { path: { base_id: base.id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover a base"));
    },
    onSuccess: () => {
      toast.success(`${base.name} removida`);
      void queryClient.invalidateQueries({ queryKey: ["knowledge-bases"] });
      router.push("/conhecimento");
    },
  });

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="kb-edit-name">Nome</FieldLabel>
          <input
            id="kb-edit-name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="kb-edit-description">Descrição</FieldLabel>
          <textarea
            id="kb-edit-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className={`${inputCls} resize-y`}
          />
          <FieldDescription>
            O agente lê a descrição para decidir quando buscar aqui.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="kb-edit-chunk">Tamanho do trecho (caracteres)</FieldLabel>
          <input
            id="kb-edit-chunk"
            type="number"
            min={200}
            max={8000}
            step={100}
            value={chunkSize}
            onChange={(e) => setChunkSize(Number(e.target.value))}
            className={inputCls}
          />
          <FieldDescription>Vale para documentos enviados depois da mudança.</FieldDescription>
        </Field>
      </FieldGroup>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-[13px]">
        <div>
          <dt className="text-[var(--text-label)]">Busca do agente</dt>
          <dd className="text-foreground">
            <code>buscar_{base.slug}</code>
          </dd>
        </div>
        <div>
          <dt className="text-[var(--text-label)]">Embedder</dt>
          <dd className="text-foreground">
            {base.embedder_model} · {base.dimensions} dimensões
          </dd>
        </div>
      </dl>
      <div className="border-border flex items-center justify-between gap-2 border-t pt-4">
        {confirmDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-[13px] text-amber-400">Remove todos os documentos.</span>
            <Button
              variant="destructive"
              onClick={() => remove.mutate()}
              disabled={remove.isPending}
            >
              Confirmar remoção
            </Button>
            <Button variant="muted" onClick={() => setConfirmDelete(false)}>
              Manter
            </Button>
          </div>
        ) : (
          <Button variant="subtleDestructive" onClick={() => setConfirmDelete(true)}>
            Remover base
          </Button>
        )}
        <Button type="submit" variant="strong" disabled={save.isPending}>
          {save.isPending ? "Salvando…" : "Salvar"}
        </Button>
      </div>
      {remove.isError && (
        <p className="text-destructive text-[13px]" role="alert">
          {remove.error.message}
        </p>
      )}
    </form>
  );
}

export default function KnowledgeBasePage() {
  const { id } = useParams<{ id: string }>();
  const { data: base, isPending, isError } = useKnowledgeBase(id);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center gap-3 border-b px-6">
        <Link
          href="/conhecimento"
          aria-label="Voltar"
          className="text-muted-foreground hover:border-border hover:text-foreground rounded border border-transparent p-1 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
        </Link>
        <span className="text-foreground text-[13px] font-medium">{base?.name ?? "Base"}</span>
        {base && <span className="text-muted-foreground text-[11px]">{base.embedder_model}</span>}
      </header>

      <main className="mx-auto w-full max-w-4xl px-6 pt-2 pb-6">
        {isPending && <p className="text-muted-foreground py-4 text-[13px]">Carregando…</p>}
        {isError && (
          <p className="text-destructive py-4 text-[13px]" role="alert">
            Não foi possível carregar a base.
          </p>
        )}
        {base && (
          <Tabs defaultValue="documentos">
            <TabsList>
              <TabsTrigger value="documentos">
                <FileText />
                Documentos
              </TabsTrigger>
              <TabsTrigger value="busca">
                <Search />
                Busca de teste
              </TabsTrigger>
              <TabsTrigger value="config">
                <Settings2 />
                Configuração
              </TabsTrigger>
            </TabsList>
            <TabsContent value="documentos" className="pt-5">
              <Documents baseId={base.id} />
            </TabsContent>
            <TabsContent value="busca" className="pt-5">
              <TestSearch baseId={base.id} />
            </TabsContent>
            <TabsContent value="config" className="pt-5">
              <Settings base={base} />
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
}
