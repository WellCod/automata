"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, BarChart2, FlaskConical, History } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { CostPanel } from "@/components/cost-panel";
import { LintPanel } from "@/components/lint-panel";
import { ModelSelector } from "@/components/model-selector";
import { TestPanel } from "@/components/test-panel";
import { VersionsPanel } from "@/components/versions-panel";
import client from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { components } from "@/lib/api/schema.d.ts";

type AgentConfigDetail = components["schemas"]["AgentConfigDetail"];

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
  capabilities: z.object({
    extended_thinking: z.boolean(),
    structured_output: z.boolean(),
    vision: z.boolean(),
  }),
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

const EMPTY_CAPS = { extended_thinking: false, structured_output: false, vision: false };

const PANEL_TABS = [
  { id: "teste" as const, label: "Teste", icon: FlaskConical },
  { id: "versoes" as const, label: "Versões", icon: History },
  { id: "custo" as const, label: "Custo", icon: BarChart2 },
  { id: "linter" as const, label: "Linter", icon: AlertTriangle },
];

type PanelId = (typeof PANEL_TABS)[number]["id"];

const inputCls =
  "w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-900 transition-colors focus:border-zinc-400 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500";
const textareaCls = `${inputCls} min-h-24 resize-y`;

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
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

function StatusBadge({ data }: { data: AgentConfigDetail | undefined }) {
  if (!data) return null;
  if (data.current_version && data.draft_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:ring-amber-800">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        rascunho pendente
      </span>
    );
  }
  if (data.current_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700 ring-1 ring-green-200 dark:bg-green-950/40 dark:text-green-400 dark:ring-green-800">
        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />v
        {data.current_version.version_number} ativo
      </span>
    );
  }
  if (data.draft_version) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:ring-amber-800">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
        rascunho
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-400 ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-600 dark:ring-zinc-700">
      sem versão
    </span>
  );
}

export default function AgentEditPage() {
  const { id } = useParams<{ id: string }>();
  const [activePanel, setActivePanel] = useState<PanelId>("teste");
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
      capabilities: EMPTY_CAPS,
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
      capabilities: data.payload?.capabilities ?? EMPTY_CAPS,
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
            capabilities: values.capabilities,
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
      <div className="flex h-14 items-center border-b border-zinc-200 bg-white px-6 dark:border-zinc-800 dark:bg-zinc-950">
        <span className="sr-only">Carregando…</span>
        <div className="h-4 w-48 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-800" />
      </div>
    );
  }

  const getPayload = () => {
    const values = form.getValues();
    if (!values.model_id) return null;
    return {
      schema_version: 1 as const,
      model_id: values.model_id,
      instructions: values.instructions,
      tools: data?.payload?.tools ?? [],
      capabilities: values.capabilities,
      metadata: data?.payload?.metadata ?? {},
    };
  };

  return (
    <div className="flex min-h-screen flex-col">
      {/* Sticky header */}
      <header className="sticky top-0 z-10 flex h-14 flex-none items-center justify-between border-b border-zinc-200 bg-white/95 px-6 backdrop-blur-sm transition-colors dark:border-zinc-800 dark:bg-zinc-950/95">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="rounded-lg p-1 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
            aria-label="Voltar"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {data?.name ?? "Agente"}
          </span>
          <StatusBadge data={data} />
        </div>
        <div className="flex items-center gap-3">
          {mutation.isSuccess && (
            <span className="text-xs text-green-600 dark:text-green-500">Salvo</span>
          )}
          {mutation.isError && (
            <span className="text-xs text-red-500 dark:text-red-400">Erro ao salvar</span>
          )}
          <button
            type="submit"
            form="agent-form"
            disabled={mutation.isPending}
            className="rounded-lg bg-zinc-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
          >
            {mutation.isPending ? "Salvando…" : "Salvar rascunho"}
          </button>
        </div>
      </header>

      {/* Two-column body */}
      <div className="flex flex-1">
        {/* Left: form */}
        <div className="min-w-0 flex-1 px-8 py-6">
          <form
            id="agent-form"
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            className="mx-auto flex max-w-2xl flex-col gap-5"
          >
            <Field label="Nome" required error={form.formState.errors.name?.message}>
              <input {...form.register("name")} className={inputCls} />
            </Field>

            <Field label="Descrição" error={form.formState.errors.description?.message}>
              <textarea {...form.register("description")} className={textareaCls} rows={2} />
            </Field>

            <Controller
              name="model_id"
              control={form.control}
              render={({ field, fieldState }) => (
                <ModelSelector
                  value={field.value}
                  capabilities={form.watch("capabilities")}
                  onChange={(modelId, caps) => {
                    field.onChange(modelId);
                    form.setValue("capabilities", caps, { shouldValidate: true });
                  }}
                  error={fieldState.error?.message}
                />
              )}
            />

            <fieldset className="flex flex-col gap-4 rounded-xl border border-zinc-200 px-4 pt-3 pb-4 transition-colors dark:border-zinc-700">
              <legend className="px-1 text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Instruções
              </legend>
              {(Object.keys(INSTRUCTION_LABELS) as (keyof typeof INSTRUCTION_LABELS)[]).map(
                (key) => (
                  <Field key={key} label={INSTRUCTION_LABELS[key]}>
                    <textarea
                      {...form.register(`instructions.${key}`)}
                      className={textareaCls}
                      rows={3}
                    />
                  </Field>
                ),
              )}
            </fieldset>
          </form>
        </div>

        {/* Right: tabbed panels */}
        <div className="w-[400px] flex-none border-l border-zinc-200 bg-white transition-colors lg:sticky lg:top-14 lg:max-h-[calc(100vh-3.5rem)] lg:overflow-y-auto dark:border-zinc-800 dark:bg-zinc-950">
          {/* Tab nav */}
          <div className="flex border-b border-zinc-200 dark:border-zinc-800">
            {PANEL_TABS.map(({ id: pid, label, icon: Icon }) => (
              <button
                key={pid}
                type="button"
                onClick={() => setActivePanel(pid)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1 px-1 py-2.5 text-xs font-medium transition-colors",
                  activePanel === pid
                    ? "border-b-2 border-zinc-900 text-zinc-900 dark:border-zinc-100 dark:text-zinc-100"
                    : "text-zinc-400 hover:text-zinc-700 dark:text-zinc-600 dark:hover:text-zinc-400",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Panel content */}
          <div className="p-4">
            {activePanel === "teste" && (
              <TestPanel agentId={id} draftVersionId={data?.draft_version?.id} defaultOpen />
            )}
            {activePanel === "versoes" && <VersionsPanel agentId={id} />}
            {activePanel === "custo" && <CostPanel agentId={id} />}
            {activePanel === "linter" && <LintPanel getPayload={getPayload} />}
          </div>
        </div>
      </div>
    </div>
  );
}
