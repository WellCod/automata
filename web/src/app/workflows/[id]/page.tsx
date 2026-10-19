"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, History } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";
import { RunsPanel } from "@/components/runs-panel";
import { VersionsPanel } from "@/components/versions-panel";
import { WorkflowEditor } from "@/components/workflow-editor";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { useUnsavedChangesWarning } from "@/lib/use-unsaved-changes";
import { cn } from "@/lib/utils";
import { structureErrors, type WorkflowNode } from "@/lib/workflow-tree";
import { Button } from "@/components/ui/button";

const schema = z.object({
  name: z.string().min(1, "Nome obrigatório"),
  description: z.string().min(1, "Descrição obrigatória"),
  // estrutura conferida por structureErrors e de novo pela API
  steps: z.custom<WorkflowNode[]>(),
});

type FormValues = z.infer<typeof schema>;

const PANEL_TABS = [
  { id: "versoes" as const, label: "Versões", icon: History },
  { id: "runs" as const, label: "Execuções", icon: Activity },
];
type PanelId = (typeof PANEL_TABS)[number]["id"];

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

export default function WorkflowEditPage() {
  const { id } = useParams<{ id: string }>();
  const fieldId = useId();
  const queryClient = useQueryClient();
  const [activePanel, setActivePanel] = useState<PanelId>("versoes");

  const { data, isPending } = useQuery({
    queryKey: ["config", id],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}", {
        params: { path: { config_id: id } },
      });
      if (res.error) throw new Error("Falha ao carregar workflow");
      return res.data!;
    },
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", description: "", steps: [] },
  });
  const { reset } = form;
  const isDirty = form.formState.isDirty;
  useUnsavedChangesWarning(isDirty);

  useEffect(() => {
    if (!data) return;
    reset({
      name: data.name,
      description: data.description,
      steps: data.payload?.workflow?.steps ?? [],
    });
  }, [data, reset]);

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const pendencias = structureErrors(values.steps);
      if (pendencias.length > 0) throw new Error(pendencias[0]);
      const res = await client.PUT("/api/v1/configs/{config_id}/draft", {
        params: { path: { config_id: id } },
        body: {
          name: values.name,
          description: values.description,
          payload: {
            schema_version: 2,
            model_id: null,
            metadata: data?.payload?.metadata ?? {},
            workflow: { steps: values.steps },
          },
        },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar rascunho"));
      return res.data!;
    },
    onSuccess: (_, values) => {
      reset(values);
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      void queryClient.invalidateQueries({ queryKey: ["config", id] });
      void queryClient.invalidateQueries({ queryKey: ["versions", id] });
    },
  });

  if (isPending) {
    return (
      <div className="border-border bg-background flex h-11 items-center border-b px-6">
        <span className="sr-only">Carregando…</span>
        <div className="bg-muted h-3.5 w-48 animate-pulse rounded" />
      </div>
    );
  }

  const errors = form.formState.errors;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <nav aria-label="Trilha" className="flex items-center gap-2 text-[13px]">
          <Link
            href="/workflows"
            className="text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Workflows
          </Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-foreground font-medium">{data?.name ?? "Workflow"}</span>
        </nav>
        <div className="flex items-center gap-3">
          {save.isError && (
            <span className="text-destructive text-[11px]" role="alert">
              {save.error.message}
            </span>
          )}
          {save.isSuccess && !isDirty && <span className="text-accent text-[11px]">Salvo</span>}
          <Button type="submit" form="workflow-form" disabled={save.isPending} variant="strong">
            {save.isPending ? "Salvando…" : "Salvar rascunho"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 flex-col lg:flex-row">
        <div className="min-w-0 flex-1 px-6 py-6 lg:px-8">
          <form
            id="workflow-form"
            onSubmit={form.handleSubmit((v) => save.mutate(v))}
            className="mx-auto flex max-w-3xl flex-col gap-5"
          >
            <div className="flex flex-col gap-1">
              <label
                htmlFor={`${fieldId}-name`}
                className="text-foreground text-[13px] font-medium"
              >
                Nome<span className="text-destructive ml-0.5">*</span>
              </label>
              <input id={`${fieldId}-name`} {...form.register("name")} className={inputCls} />
              {errors.name && <p className="text-destructive text-[11px]">{errors.name.message}</p>}
            </div>

            <div className="flex flex-col gap-1">
              <label
                htmlFor={`${fieldId}-desc`}
                className="text-foreground text-[13px] font-medium"
              >
                Descrição<span className="text-destructive ml-0.5">*</span>
              </label>
              <textarea
                id={`${fieldId}-desc`}
                {...form.register("description")}
                rows={2}
                className={`${inputCls} resize-y`}
              />
              {errors.description && (
                <p className="text-destructive text-[11px]">{errors.description.message}</p>
              )}
            </div>

            <Controller
              name="steps"
              control={form.control}
              render={({ field }) => (
                <WorkflowEditor value={field.value} onChange={field.onChange} />
              )}
            />
          </form>
        </div>

        <aside className="border-border bg-background w-full flex-none border-t lg:sticky lg:top-11 lg:max-h-[calc(100vh-2.75rem)] lg:w-[400px] lg:overflow-y-auto lg:border-t-0 lg:border-l">
          <div
            className="border-border flex border-b"
            role="tablist"
            aria-label="Painéis do workflow"
          >
            {PANEL_TABS.map(({ id: pid, label, icon: Icon }) => (
              <button
                key={pid}
                type="button"
                role="tab"
                aria-selected={activePanel === pid}
                onClick={() => setActivePanel(pid)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1 px-1 py-2.5 text-[11px] font-medium transition-colors",
                  activePanel === pid
                    ? "border-accent text-accent border-b"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {label}
              </button>
            ))}
          </div>
          <div className="p-4" role="tabpanel">
            {activePanel === "versoes" && (
              <VersionsPanel
                agentId={id}
                currentVersionId={data?.current_version?.id}
                hasUnsavedChanges={isDirty}
              />
            )}
            {activePanel === "runs" && <RunsPanel agentId={id} />}
          </div>
        </aside>
      </div>
    </div>
  );
}
