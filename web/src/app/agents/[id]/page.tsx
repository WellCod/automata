"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import client from "@/lib/api/client";

const instructionSchema = z.object({
  persona: z.string(),
  situation: z.string(),
  tone: z.string(),
  objective: z.string(),
  guardrails: z.string(),
});

const schema = z.object({
  name: z.string().min(1, "Nome obrigatório"),
  description: z.string().optional(),
  model_id: z.string().min(1, "Modelo obrigatório"),
  instructions: instructionSchema,
});

type FormValues = z.infer<typeof schema>;

const INSTRUCTION_LABELS: Record<keyof z.infer<typeof instructionSchema>, string> = {
  persona: "Persona",
  situation: "Situação",
  tone: "Tom",
  objective: "Objetivo",
  guardrails: "Guardrails",
};

function Field({
  label,
  error,
  children,
  required,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
  required?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-zinc-700">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

const inputCls =
  "rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-900 focus:border-zinc-400 focus:outline-none";
const textareaCls = `${inputCls} min-h-24 resize-y`;

export default function AgentEditPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data, isPending: isLoading } = useQuery({
    queryKey: ["config", id],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}", {
        params: { path: { config_id: id } },
      });
      if (res.error) throw new Error("Falha ao carregar agente");
      return res.data!;
    },
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: "",
      description: "",
      model_id: "",
      instructions: { persona: "", situation: "", tone: "", objective: "", guardrails: "" },
    },
  });

  const { reset } = form;
  useEffect(() => {
    if (!data) return;
    reset({
      name: data.name,
      description: data.description ?? "",
      model_id: data.payload?.model_id ?? "",
      instructions: {
        persona: data.payload?.instructions?.persona ?? "",
        situation: data.payload?.instructions?.situation ?? "",
        tone: data.payload?.instructions?.tone ?? "",
        objective: data.payload?.instructions?.objective ?? "",
        guardrails: data.payload?.instructions?.guardrails ?? "",
      },
    });
  }, [data, reset]);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const res = await client.PUT("/api/v1/configs/{config_id}/draft", {
        params: { path: { config_id: id } },
        body: {
          name: values.name,
          description: values.description || null,
          payload: {
            schema_version: 1,
            model_id: values.model_id,
            instructions: values.instructions,
            tools: data?.payload?.tools ?? [],
            capabilities: data?.payload?.capabilities ?? {
              extended_thinking: false,
              structured_output: false,
              vision: false,
            },
            metadata: data?.payload?.metadata ?? {},
          },
        },
      });
      if (res.error) throw new Error("Falha ao salvar rascunho");
      return res.data!;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      void queryClient.invalidateQueries({ queryKey: ["config", id] });
    },
  });

  if (isLoading) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
        <div className="text-sm text-zinc-400">Carregando…</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Agentes
      </Link>

      <h1 className="mb-6 text-2xl font-semibold text-zinc-900">{data?.name ?? "Agente"}</h1>

      <form onSubmit={form.handleSubmit((v) => mutation.mutate(v))} className="flex flex-col gap-5">
        <Field label="Nome" required error={form.formState.errors.name?.message}>
          <input {...form.register("name")} className={inputCls} />
        </Field>

        <Field label="Descrição" error={form.formState.errors.description?.message}>
          <textarea {...form.register("description")} className={textareaCls} rows={2} />
        </Field>

        <Field label="Modelo" required error={form.formState.errors.model_id?.message}>
          <input
            {...form.register("model_id")}
            className={inputCls}
            placeholder="ex: claude-sonnet-4-6"
          />
        </Field>

        <fieldset className="flex flex-col gap-4 rounded-lg border border-zinc-200 px-4 pt-3 pb-4">
          <legend className="px-1 text-sm font-medium text-zinc-700">Instruções</legend>
          {(Object.keys(INSTRUCTION_LABELS) as (keyof typeof INSTRUCTION_LABELS)[]).map((key) => (
            <Field key={key} label={INSTRUCTION_LABELS[key]}>
              <textarea
                {...form.register(`instructions.${key}`)}
                className={textareaCls}
                rows={3}
              />
            </Field>
          ))}
        </fieldset>

        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Salvando…" : "Salvar rascunho"}
          </button>
          {mutation.isSuccess && (
            <span className="text-sm text-green-600">Salvo como rascunho</span>
          )}
          {mutation.isError && (
            <span className="text-sm text-red-500">Erro ao salvar. Tente novamente.</span>
          )}
        </div>
      </form>
    </div>
  );
}
