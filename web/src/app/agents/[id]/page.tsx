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
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";
const textareaCls = `${inputCls} min-h-24 resize-y`;

function FieldLabel({ label, required }: { label: string; required?: boolean }) {
  return (
    <label className="text-muted-foreground text-[11px] font-medium tracking-[0.05em] uppercase">
      {label}
      {required && <span className="text-destructive ml-0.5">*</span>}
    </label>
  );
}

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
      <FieldLabel label={label} required={required} />
      {children}
      {error && <p className="text-destructive text-[11px]">{error}</p>}
    </div>
  );
}

function AgentStatusBadge({ data }: { data: AgentConfigDetail | undefined }) {
  if (!data) return null;
  if (data.current_version && data.draft_version) {
    return (
      <span className="text-[11px] tracking-[0.05em] text-amber-400 uppercase">
        v{data.current_version.version_number} · rascunho pendente
      </span>
    );
  }
  if (data.current_version) {
    return (
      <span className="text-accent text-[11px] tracking-[0.05em] uppercase">
        v{data.current_version.version_number} · ativo
      </span>
    );
  }
  if (data.draft_version) {
    return (
      <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
        rascunho
      </span>
    );
  }
  return (
    <span className="text-muted-foreground text-[11px] tracking-[0.05em] uppercase">
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
      <div className="border-border flex h-11 items-center border-b px-6">
        <span className="sr-only">Carregando…</span>
        <div className="bg-muted h-3 w-40 animate-pulse rounded" />
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
      {/* Header */}
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-muted-foreground hover:text-foreground transition-colors"
            aria-label="Voltar"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <span className="text-foreground text-sm font-medium">{data?.name ?? "Agente"}</span>
          <AgentStatusBadge data={data} />
        </div>
        <div className="flex items-center gap-4">
          {mutation.isSuccess && (
            <span className="text-accent text-[11px] tracking-[0.05em] uppercase">Salvo</span>
          )}
          {mutation.isError && (
            <span className="text-destructive text-[11px] tracking-[0.05em] uppercase">
              Erro ao salvar
            </span>
          )}
          <button
            type="submit"
            form="agent-form"
            disabled={mutation.isPending}
            className="border-foreground text-foreground hover:border-accent hover:text-accent rounded border px-3 py-1 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors disabled:opacity-40"
          >
            {mutation.isPending ? "Salvando…" : "Salvar rascunho"}
          </button>
        </div>
      </header>

      {/* Two-column body */}
      <div className="flex flex-1">
        {/* Left: form */}
        <div className="min-w-0 flex-1 px-6 py-4">
          <form
            id="agent-form"
            onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
            className="flex max-w-2xl flex-col gap-4"
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

            <fieldset className="border-border flex flex-col gap-3 rounded border px-4 pt-3 pb-4">
              <legend className="text-muted-foreground px-1 text-[11px] font-medium tracking-[0.05em] uppercase">
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
        <div className="border-border bg-background w-[360px] flex-none border-l lg:sticky lg:top-11 lg:max-h-[calc(100vh-2.75rem)] lg:overflow-y-auto">
          {/* Tab nav */}
          <div className="border-border flex border-b">
            {PANEL_TABS.map(({ id: pid, label, icon: Icon }) => (
              <button
                key={pid}
                type="button"
                onClick={() => setActivePanel(pid)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1 px-1 py-2 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors",
                  activePanel === pid
                    ? "border-accent text-accent border-b"
                    : "text-muted-foreground hover:text-foreground",
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
