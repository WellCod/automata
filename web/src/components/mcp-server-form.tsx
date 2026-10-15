"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useId, useState } from "react";
import { useFieldArray, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import type { McpServer } from "@/components/mcp-tools-selector";
import { Button } from "@/components/ui/button";

const schema = z.object({
  name: z.string().min(1, "Nome obrigatório").max(255),
  slug: z
    .string()
    .regex(
      /^[a-z][a-z0-9_]{1,30}$/,
      "Minúsculas, números e _; começa com letra; 2 a 31 caracteres",
    ),
  url: z.string().url("URL inválida"),
  timeout_seconds: z.number().int().min(1).max(120),
  headers: z.array(
    z.object({
      name: z.string().regex(/^[A-Za-z0-9-]{1,64}$/, "Nome de header inválido"),
      value: z.string().min(1, "Valor obrigatório"),
    }),
  ),
});

type FormValues = z.infer<typeof schema>;

export type McpServerBody = {
  name: string;
  slug: string;
  url: string;
  timeout_seconds: number;
  // null mantém os headers salvos; {} apaga
  headers: Record<string, string> | null;
};

interface Props {
  server?: McpServer;
  pending: boolean;
  error?: string;
  onSubmit: (body: McpServerBody) => void;
  onCancel: () => void;
}

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

export function slugify(name: string): string {
  const slug = name
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 31);
  return /^[a-z]/.test(slug) ? slug : `mcp_${slug}`.slice(0, 31);
}

export function McpServerForm({ server, pending, error, onSubmit, onCancel }: Props) {
  const id = useId();
  const editing = server !== undefined;
  // Na edição, os headers salvos só são reenviados se o usuário decidir substituí-los
  const [replaceHeaders, setReplaceHeaders] = useState(!editing);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: server?.name ?? "",
      slug: server?.slug ?? "",
      url: server?.url ?? "https://",
      timeout_seconds: server?.timeout_seconds ?? 30,
      headers: [],
    },
  });
  const headers = useFieldArray({ control: form.control, name: "headers" });
  const slug = useWatch({ control: form.control, name: "slug" });
  const errors = form.formState.errors;

  function submit(values: FormValues) {
    onSubmit({
      name: values.name,
      slug: values.slug,
      url: values.url,
      timeout_seconds: values.timeout_seconds,
      headers: replaceHeaders
        ? Object.fromEntries(values.headers.map((h) => [h.name, h.value]))
        : null,
    });
  }

  return (
    <form
      onSubmit={form.handleSubmit(submit)}
      className="border-border bg-card flex flex-col gap-4 rounded border p-4"
      aria-label={editing ? `Editar ${server.name}` : "Novo servidor MCP"}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-name`} className="text-foreground text-[13px] font-medium">
            Nome
          </label>
          <input
            id={`${id}-name`}
            {...form.register("name", {
              onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
                if (!editing && !form.getFieldState("slug").isDirty) {
                  form.setValue("slug", slugify(e.target.value));
                }
              },
            })}
            className={inputCls}
            aria-invalid={errors.name ? true : undefined}
          />
          {errors.name && <p className="text-destructive text-[11px]">{errors.name.message}</p>}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-slug`} className="text-foreground text-[13px] font-medium">
            Slug
          </label>
          <input
            id={`${id}-slug`}
            {...form.register("slug")}
            className={inputCls}
            aria-describedby={`${id}-slug-hint`}
            aria-invalid={errors.slug ? true : undefined}
          />
          <p id={`${id}-slug-hint`} className="text-muted-foreground text-[11px]">
            Vira o prefixo das tools: <code>{slug || "slug"}_nome_da_tool</code>
          </p>
          {errors.slug && <p className="text-destructive text-[11px]">{errors.slug.message}</p>}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-[1fr_120px]">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-url`} className="text-foreground text-[13px] font-medium">
            URL (streamable HTTP)
          </label>
          <input
            id={`${id}-url`}
            {...form.register("url")}
            className={inputCls}
            aria-invalid={errors.url ? true : undefined}
          />
          {errors.url && <p className="text-destructive text-[11px]">{errors.url.message}</p>}
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${id}-timeout`} className="text-foreground text-[13px] font-medium">
            Timeout (s)
          </label>
          <input
            id={`${id}-timeout`}
            type="number"
            min={1}
            max={120}
            {...form.register("timeout_seconds", { valueAsNumber: true })}
            className={inputCls}
          />
        </div>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="text-foreground text-[13px] font-medium">Headers</legend>
        <p className="text-muted-foreground text-[11px]">
          Credenciais ficam cifradas na API e nunca voltam para o painel.
        </p>
        {editing && !replaceHeaders ? (
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted-foreground text-[13px]">
              {server.header_names.length > 0
                ? `Salvos: ${server.header_names.join(", ")}`
                : "Nenhum header salvo"}
            </span>
            <Button onClick={() => setReplaceHeaders(true)} variant="muted">
              Substituir headers
            </Button>
          </div>
        ) : (
          <>
            {headers.fields.map((field, index) => (
              <div key={field.id} className="flex items-start gap-2">
                <input
                  {...form.register(`headers.${index}.name`)}
                  placeholder="Authorization"
                  aria-label={`Nome do header ${index + 1}`}
                  className={inputCls}
                />
                <input
                  {...form.register(`headers.${index}.value`)}
                  type="password"
                  autoComplete="off"
                  placeholder="Bearer …"
                  aria-label={`Valor do header ${index + 1}`}
                  className={inputCls}
                />
                <Button
                  onClick={() => headers.remove(index)}
                  variant="subtleDestructive"
                  className="flex-none"
                  aria-label={`Remover header ${index + 1}`}
                >
                  ×
                </Button>
              </div>
            ))}
            {errors.headers && (
              <p className="text-destructive text-[11px]">Confira nome e valor dos headers.</p>
            )}
            <div className="flex gap-2">
              <Button onClick={() => headers.append({ name: "", value: "" })} variant="muted">
                Adicionar header
              </Button>
              {editing && (
                <span className="text-muted-foreground self-center text-[11px]">
                  Salvar substitui todos os headers. Sem nenhum, os atuais são apagados.
                </span>
              )}
            </div>
          </>
        )}
      </fieldset>

      {error && (
        <p className="text-destructive text-[13px]" role="alert">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <Button onClick={onCancel} variant="muted">
          Cancelar
        </Button>
        <Button type="submit" disabled={pending} variant="strong">
          {pending ? "Salvando…" : "Salvar"}
        </Button>
      </div>
    </form>
  );
}
