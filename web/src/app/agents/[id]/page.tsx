"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, FlaskConical, History, Settings2, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { CostPanel } from "@/components/cost-panel";
import { LintPanel } from "@/components/lint-panel";
import { KnowledgeSelector } from "@/components/knowledge-selector";
import { McpToolsSelector } from "@/components/mcp-tools-selector";
import { MetricsPanel } from "@/components/metrics-panel";
import { ModelSelector } from "@/components/model-selector";
import { RunsPanel } from "@/components/runs-panel";
import { TestPanel } from "@/components/test-panel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/status-badge";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { VersionsPanel } from "@/components/versions-panel";
import client from "@/lib/api/client";
import { useUnsavedChangesWarning } from "@/lib/use-unsaved-changes";
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
  mcp_servers: z.array(
    z.object({
      server_id: z.string(),
      tools: z.array(z.string()).nullable(),
      require_confirmation: z.array(z.string()),
    }),
  ),
  knowledge: z.array(
    z.object({ base_id: z.string(), max_results: z.number().int().min(1).max(20) }),
  ),
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

const PAGE_TABS = [
  { id: "config" as const, label: "Configuração", icon: Settings2 },
  { id: "runs" as const, label: "Execuções", icon: Activity },
  { id: "desempenho" as const, label: "Desempenho", icon: TrendingUp },
  { id: "versoes" as const, label: "Versões", icon: History },
];

type PageTab = (typeof PAGE_TABS)[number]["id"];

const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";
const textareaCls = `${inputCls} min-h-24 resize-y`;

function StatusBadge({ data }: { data: AgentConfigDetail | undefined }) {
  if (!data) return null;
  if (data.current_version && data.draft_version) {
    return <Badge tone="pending">Rascunho pendente</Badge>;
  }
  if (data.current_version) {
    return <Badge tone="active">v{data.current_version.version_number} ativa</Badge>;
  }
  if (data.draft_version) {
    return <Badge tone="pending">Rascunho</Badge>;
  }
  return <Badge tone="neutral">Sem versão</Badge>;
}

// Publicar o agente muda o comportamento destes times (ADR-0011)
function TeamsUsingAgent({ agentId }: { agentId: string }) {
  const { data: teams } = useQuery({
    queryKey: ["config", agentId, "teams"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/teams", {
        params: { path: { config_id: agentId } },
      });
      if (res.error) throw new Error("Falha ao carregar times");
      return res.data!;
    },
  });
  // aviso secundário: resposta inesperada não pode derrubar a tela de edição
  if (!Array.isArray(teams) || teams.length === 0) return null;
  return (
    <p className="border-border text-muted-foreground rounded border px-3 py-2 text-[13px]">
      Membro de{" "}
      {teams.map((t, i) => (
        <span key={t.id}>
          {i > 0 && ", "}
          <Link href={`/times/${t.id}`} className="text-accent hover:underline">
            {t.name}
          </Link>
        </span>
      ))}
      . Publicar este agente muda o comportamento desses times.
    </p>
  );
}

export default function AgentEditPage() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<PageTab>("config");
  const queryClient = useQueryClient();

  const {
    data,
    isPending: isLoading,
    isError,
    refetch,
  } = useQuery({
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
      mcp_servers: [],
      knowledge: [],
    },
  });

  const { reset } = form;
  const isDirty = form.formState.isDirty;
  useUnsavedChangesWarning(isDirty);

  // refetch (foco na janela, invalidação) não pode apagar o que ainda não foi salvo
  const dirtyRef = useRef(isDirty);
  useEffect(() => {
    dirtyRef.current = isDirty;
  }, [isDirty]);

  useEffect(() => {
    if (!data || dirtyRef.current) return;
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
      mcp_servers: (data.payload?.mcp_servers ?? []).map((b) => ({
        server_id: b.server_id,
        tools: b.tools ?? null,
        require_confirmation: b.require_confirmation ?? [],
      })),
      knowledge: (data.payload?.knowledge ?? []).map((k) => ({
        base_id: k.base_id,
        max_results: k.max_results ?? 5,
      })),
    });
  }, [data, reset]);

  const mutation = useMutation({
    mutationFn: async (values: FormValues) => {
      const res = await client.PUT("/api/v1/configs/{config_id}/draft", {
        params: { path: { config_id: id } },
        body: {
          name: values.name,
          description: values.description ?? "",
          payload: {
            schema_version: 2,
            model_id: values.model_id,
            instructions: values.instructions,
            mcp_servers: values.mcp_servers,
            capabilities: values.capabilities,
            knowledge: values.knowledge,
            // o painel ainda não edita guardrails: preserva os da versão carregada
            guardrails: data?.payload?.guardrails,
            metadata: data?.payload?.metadata ?? {},
          },
        },
      });
      if (res.error) throw new Error("Falha ao salvar rascunho");
      return res.data!;
    },
    onSuccess: (_, values) => {
      dirtyRef.current = false;
      reset(values);
      void queryClient.invalidateQueries({ queryKey: ["configs"] });
      void queryClient.invalidateQueries({ queryKey: ["config", id] });
      toast.success("Rascunho salvo");
    },
    onError: () => {
      toast.error("Erro ao salvar rascunho");
    },
  });

  if (isLoading) {
    return (
      <div className="border-border bg-background flex h-11 items-center border-b px-6">
        <span className="sr-only">Carregando…</span>
        <div className="bg-muted h-3.5 w-48 animate-pulse rounded" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-start gap-3 px-6 py-6">
        <p className="text-destructive text-[13px]">Erro ao carregar o agente.</p>
        <div className="flex gap-2">
          <Button onClick={() => void refetch()}>Tentar de novo</Button>
          <Link
            href="/"
            className="border-border text-muted-foreground hover:text-foreground inline-flex h-7 items-center rounded border px-3 text-[11px] font-medium transition-colors"
          >
            Voltar
          </Link>
        </div>
      </div>
    );
  }

  const getPayload = () => {
    const values = form.getValues();
    if (!values.model_id) return null;
    return {
      schema_version: 2 as const,
      model_id: values.model_id,
      instructions: values.instructions,
      mcp_servers: values.mcp_servers,
      capabilities: values.capabilities,
      knowledge: values.knowledge,
      // o painel ainda não edita guardrails: preserva os da versão carregada
      guardrails: data?.payload?.guardrails,
      metadata: data?.payload?.metadata ?? {},
    };
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-border bg-background sticky top-0 z-10 flex h-11 flex-none items-center justify-between border-b px-6">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-muted-foreground hover:border-border hover:text-foreground rounded border border-transparent p-1 transition-colors"
            aria-label="Voltar"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </Link>
          <span className="text-foreground text-[13px] font-medium">{data?.name ?? "Agente"}</span>
          <StatusBadge data={data} />
        </div>
        <div className="flex items-center gap-3">
          {isDirty && !mutation.isPending && (
            <span className="text-[11px] text-amber-600 dark:text-amber-400">
              Alterações não salvas
            </span>
          )}
          <Button type="submit" form="agent-form" variant="strong" disabled={mutation.isPending}>
            {mutation.isPending ? "Salvando…" : "Salvar rascunho"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1">
        <Tabs
          value={tab}
          onValueChange={(v) => setTab(v as PageTab)}
          className="min-w-0 flex-1 px-8 pt-2 pb-6"
        >
          <TabsList>
            {PAGE_TABS.map(({ id: tid, label, icon: Icon }) => (
              <TabsTrigger key={tid} value={tid}>
                <Icon />
                {label}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* sempre montada: o botão do cabeçalho submete o form de qualquer aba */}
          <TabsContent value="config" keepMounted className="pt-5">
            <form
              id="agent-form"
              onSubmit={form.handleSubmit((v) => mutation.mutate(v))}
              className="mx-auto flex max-w-2xl flex-col gap-5"
            >
              <TeamsUsingAgent agentId={id} />

              <FieldGroup>
                <Field data-invalid={!!form.formState.errors.name}>
                  <FieldLabel htmlFor="agent-name" className="gap-0.5">
                    Nome<span className="text-destructive">*</span>
                  </FieldLabel>
                  <input
                    id="agent-name"
                    {...form.register("name")}
                    aria-invalid={!!form.formState.errors.name}
                    className={inputCls}
                  />
                  <FieldError>{form.formState.errors.name?.message}</FieldError>
                </Field>

                <Field>
                  <FieldLabel htmlFor="agent-description">Descrição</FieldLabel>
                  <textarea
                    id="agent-description"
                    {...form.register("description")}
                    className={textareaCls}
                    rows={2}
                  />
                </Field>
              </FieldGroup>

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

              <Controller
                name="mcp_servers"
                control={form.control}
                render={({ field }) => (
                  <McpToolsSelector value={field.value} onChange={field.onChange} />
                )}
              />

              <Controller
                name="knowledge"
                control={form.control}
                render={({ field }) => (
                  <KnowledgeSelector value={field.value} onChange={field.onChange} />
                )}
              />

              <FieldSet className="border-border rounded border px-4 pt-3 pb-4">
                <FieldLegend className="px-1">Instruções</FieldLegend>
                <FieldGroup>
                  {(Object.keys(INSTRUCTION_LABELS) as (keyof typeof INSTRUCTION_LABELS)[]).map(
                    (key) => (
                      <Field key={key}>
                        <FieldLabel htmlFor={`instructions-${key}`}>
                          {INSTRUCTION_LABELS[key]}
                        </FieldLabel>
                        <textarea
                          id={`instructions-${key}`}
                          {...form.register(`instructions.${key}`)}
                          className={textareaCls}
                          rows={3}
                        />
                      </Field>
                    ),
                  )}
                </FieldGroup>
              </FieldSet>

              <section className="border-border rounded border px-4 py-3">
                <LintPanel getPayload={getPayload} />
              </section>
            </form>
          </TabsContent>

          <TabsContent value="runs" className="pt-5">
            <div className="mx-auto max-w-3xl">
              <RunsPanel agentId={id} />
            </div>
          </TabsContent>

          <TabsContent value="desempenho" className="pt-5">
            <div className="mx-auto flex max-w-3xl flex-col gap-6">
              <MetricsPanel agentId={id} />
              <CostPanel agentId={id} />
            </div>
          </TabsContent>

          <TabsContent value="versoes" className="pt-5">
            <div className="mx-auto max-w-3xl">
              <VersionsPanel
                agentId={id}
                currentVersionId={data?.current_version?.id}
                hasUnsavedChanges={isDirty}
              />
            </div>
          </TabsContent>
        </Tabs>

        <aside
          aria-label="Testar"
          className="border-border bg-background w-[400px] flex-none border-l lg:sticky lg:top-11 lg:max-h-[calc(100vh-2.75rem)] lg:overflow-y-auto"
        >
          <div className="border-border flex h-9 items-center gap-1.5 border-b px-4">
            <FlaskConical className="text-muted-foreground h-3.5 w-3.5" />
            <h2 className="text-foreground text-[11px] font-medium">Testar</h2>
          </div>
          <div className="p-4">
            <TestPanel agentId={id} draftVersionId={data?.draft_version?.id} defaultOpen />
          </div>
        </aside>
      </div>
    </div>
  );
}
