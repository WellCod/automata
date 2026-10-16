"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, ArrowLeft, FlaskConical, History, TrendingUp } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useMemo, useState } from "react";
import { Controller, useForm, useWatch } from "react-hook-form";
import { z } from "zod";
import { KnowledgeSelector } from "@/components/knowledge-selector";
import { McpToolsSelector } from "@/components/mcp-tools-selector";
import { MetricsPanel } from "@/components/metrics-panel";
import { ModelSelector } from "@/components/model-selector";
import { RunsPanel } from "@/components/runs-panel";
import { TeamMembersPicker, usePublishedAgents } from "@/components/team-members-picker";
import { TestPanel } from "@/components/test-panel";
import { VersionsPanel } from "@/components/versions-panel";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const MODES = [
  {
    value: "coordinate",
    label: "Coordenar",
    hint: "O líder divide a tarefa, delega a quem precisar e junta as respostas.",
  },
  {
    value: "route",
    label: "Rotear",
    hint: "O líder escolhe um membro e devolve a resposta dele sem reescrever.",
  },
  {
    value: "broadcast",
    label: "Consultar todos",
    hint: "A mesma tarefa vai para todos os membros e o líder consolida.",
  },
  {
    value: "tasks",
    label: "Tarefas",
    hint: "O líder monta uma lista de tarefas e acompanha até concluir.",
  },
] as const;

const schema = z.object({
  name: z.string().min(1, "Nome obrigatório"),
  description: z.string().min(1, "Descrição obrigatória"),
  model_id: z.string().min(1, "Modelo do líder obrigatório"),
  capabilities: z.object({
    extended_thinking: z.boolean(),
    structured_output: z.boolean(),
    vision: z.boolean(),
  }),
  instructions: z.object({
    persona: z.string(),
    situation: z.string(),
    tone: z.string(),
    objective: z.string(),
    guardrails: z.string(),
  }),
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
  team: z.object({
    mode: z.enum(["coordinate", "route", "broadcast", "tasks"]),
    members: z
      .array(z.object({ agent_id: z.string(), version_id: z.string().nullable() }))
      .min(1, "Escolha ao menos um membro"),
    max_iterations: z.number().int().min(1).max(50),
    share_member_interactions: z.boolean(),
  }),
});

type FormValues = z.infer<typeof schema>;

const INSTRUCTION_LABELS = {
  persona: "Persona do líder",
  situation: "Situação",
  tone: "Tom",
  objective: "Objetivo",
  guardrails: "Guardrails",
} as const;

const PANEL_TABS = [
  { id: "teste" as const, label: "Teste", icon: FlaskConical },
  { id: "versoes" as const, label: "Versões", icon: History },
  { id: "runs" as const, label: "Execuções", icon: Activity },
  { id: "metricas" as const, label: "Métricas", icon: TrendingUp },
];
type PanelId = (typeof PANEL_TABS)[number]["id"];

const EMPTY_CAPS = { extended_thinking: false, structured_output: false, vision: false };
const inputCls =
  "w-full rounded border border-border bg-[var(--input)] px-3 py-1.5 text-[13px] text-foreground placeholder:text-muted-foreground transition-colors focus:border-accent focus:outline-none";

export default function TeamEditPage() {
  const { id } = useParams<{ id: string }>();
  const fieldId = useId();
  const queryClient = useQueryClient();
  const [activePanel, setActivePanel] = useState<PanelId>("teste");
  const { data: agents } = usePublishedAgents();
  const memberNames = useMemo(
    () => Object.fromEntries((agents ?? []).map((a) => [a.id, a.name])),
    [agents],
  );

  const { data, isPending } = useQuery({
    queryKey: ["config", id],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}", {
        params: { path: { config_id: id } },
      });
      if (res.error) throw new Error("Falha ao carregar time");
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
      team: {
        mode: "coordinate",
        members: [],
        max_iterations: 10,
        share_member_interactions: false,
      },
    },
  });
  const mode = useWatch({ control: form.control, name: "team.mode" });
  const capabilities = useWatch({ control: form.control, name: "capabilities" });

  const { reset } = form;
  useEffect(() => {
    if (!data) return;
    const p = data.payload;
    reset({
      name: data.name,
      description: data.description,
      model_id: p?.model_id ?? "",
      capabilities: p?.capabilities ?? EMPTY_CAPS,
      instructions: {
        persona: p?.instructions?.persona ?? "",
        situation: p?.instructions?.situation ?? "",
        tone: p?.instructions?.tone ?? "",
        objective: p?.instructions?.objective ?? "",
        guardrails: p?.instructions?.guardrails ?? "",
      },
      mcp_servers: (p?.mcp_servers ?? []).map((b) => ({
        server_id: b.server_id,
        tools: b.tools ?? null,
        require_confirmation: b.require_confirmation ?? [],
      })),
      knowledge: (p?.knowledge ?? []).map((k) => ({
        base_id: k.base_id,
        max_results: k.max_results ?? 5,
      })),
      team: {
        mode: p?.team?.mode ?? "coordinate",
        members: (p?.team?.members ?? []).map((m) => ({
          agent_id: m.agent_id,
          version_id: m.version_id ?? null,
        })),
        max_iterations: p?.team?.max_iterations ?? 10,
        share_member_interactions: p?.team?.share_member_interactions ?? false,
      },
    });
  }, [data, reset]);

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const res = await client.PUT("/api/v1/configs/{config_id}/draft", {
        params: { path: { config_id: id } },
        body: {
          name: values.name,
          description: values.description,
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
            team: values.team,
          },
        },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar rascunho"));
      return res.data!;
    },
    onSuccess: () => {
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
            href="/times"
            className="text-muted-foreground hover:text-foreground flex items-center gap-1"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            Times
          </Link>
          <span className="text-muted-foreground">/</span>
          <span className="text-foreground font-medium">{data?.name ?? "Time"}</span>
        </nav>
        <div className="flex items-center gap-3">
          {save.isError && (
            <span className="text-destructive text-[11px]" role="alert">
              {save.error.message}
            </span>
          )}
          {save.isSuccess && !form.formState.isDirty && (
            <span className="text-accent text-[11px] tracking-[0.05em] uppercase">Salvo</span>
          )}
          <Button type="submit" form="team-form" disabled={save.isPending} variant="strong">
            {save.isPending ? "Salvando…" : "Salvar rascunho"}
          </Button>
        </div>
      </header>

      <div className="flex flex-1 flex-col lg:flex-row">
        <div className="min-w-0 flex-1 px-6 py-6 lg:px-8">
          <form
            id="team-form"
            onSubmit={form.handleSubmit((v) => save.mutate(v))}
            className="mx-auto flex max-w-2xl flex-col gap-5"
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

            <fieldset className="border-border flex flex-col gap-2 rounded border px-4 pt-3 pb-4">
              <legend className="text-foreground px-1 text-[13px] font-medium">
                Como o líder coordena
              </legend>
              {MODES.map((m) => (
                <label key={m.value} className="flex items-start gap-2">
                  <input
                    type="radio"
                    value={m.value}
                    {...form.register("team.mode")}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="text-foreground block text-[13px]">{m.label}</span>
                    <span className="text-muted-foreground block text-[11px]">{m.hint}</span>
                  </span>
                </label>
              ))}
              <div className="mt-2 flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-[13px]">
                  <span className="text-foreground">Máximo de iterações</span>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    {...form.register("team.max_iterations", { valueAsNumber: true })}
                    className={`${inputCls} w-20`}
                  />
                </label>
                <label className="flex items-center gap-2 text-[13px]">
                  <input type="checkbox" {...form.register("team.share_member_interactions")} />
                  <span className="text-foreground">Membros veem o que os outros responderam</span>
                </label>
              </div>
              {mode === "route" && (
                <p className="text-muted-foreground text-[11px]">
                  Em roteamento, descrições parecidas entre membros fazem o líder escolher errado.
                </p>
              )}
            </fieldset>

            <Controller
              name="team.members"
              control={form.control}
              render={({ field, fieldState }) => (
                <TeamMembersPicker
                  value={field.value}
                  onChange={field.onChange}
                  error={fieldState.error?.message}
                />
              )}
            />

            <Controller
              name="model_id"
              control={form.control}
              render={({ field, fieldState }) => (
                <ModelSelector
                  value={field.value}
                  capabilities={capabilities}
                  onChange={(modelId, caps) => {
                    field.onChange(modelId);
                    form.setValue("capabilities", caps, { shouldValidate: true });
                  }}
                  error={fieldState.error?.message}
                />
              )}
            />

            <fieldset className="border-border flex flex-col gap-4 rounded border px-4 pt-3 pb-4">
              <legend className="text-foreground px-1 text-[13px] font-medium">
                Instruções do líder
              </legend>
              {(Object.keys(INSTRUCTION_LABELS) as (keyof typeof INSTRUCTION_LABELS)[]).map(
                (key) => (
                  <div key={key} className="flex flex-col gap-1">
                    <label
                      htmlFor={`${fieldId}-${key}`}
                      className="text-foreground text-[13px] font-medium"
                    >
                      {INSTRUCTION_LABELS[key]}
                    </label>
                    <textarea
                      id={`${fieldId}-${key}`}
                      {...form.register(`instructions.${key}`)}
                      rows={3}
                      className={`${inputCls} min-h-24 resize-y`}
                    />
                  </div>
                ),
              )}
            </fieldset>

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
          </form>
        </div>

        <aside className="border-border bg-background w-full flex-none border-t lg:sticky lg:top-11 lg:max-h-[calc(100vh-2.75rem)] lg:w-[400px] lg:overflow-y-auto lg:border-t-0 lg:border-l">
          <div className="border-border flex border-b" role="tablist" aria-label="Painéis do time">
            {PANEL_TABS.map(({ id: pid, label, icon: Icon }) => (
              <button
                key={pid}
                type="button"
                role="tab"
                aria-selected={activePanel === pid}
                onClick={() => setActivePanel(pid)}
                className={cn(
                  "flex flex-1 flex-col items-center gap-1 px-1 py-2.5 text-[11px] font-medium tracking-[0.05em] uppercase transition-colors",
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
            {/* o teste fica montado: trocar de aba não apaga a conversa */}
            <div hidden={activePanel !== "teste"}>
              <TestPanel
                agentId={id}
                kind="team"
                memberNames={memberNames}
                draftVersionId={data?.draft_version?.id}
                defaultOpen
              />
            </div>
            {activePanel === "versoes" && <VersionsPanel agentId={id} />}
            {activePanel === "runs" && <RunsPanel agentId={id} />}
            {activePanel === "metricas" && <MetricsPanel agentId={id} />}
          </div>
        </aside>
      </div>
    </div>
  );
}
