"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import type { components } from "@/lib/api/schema.d.ts";
import { type EvalCaseInput, type EvalScheduleInput, runActive } from "@/lib/eval-checks";

// parâmetro de rota comum a quase todas as chamadas da suíte
const configPath = (configId: string) => ({ params: { path: { config_id: configId } } });

export function useEvalCases(configId: string, enabled = true) {
  return useQuery({
    queryKey: ["eval-cases", configId],
    enabled,
    queryFn: async () => {
      const result = await client.GET(
        "/api/v1/configs/{config_id}/eval-cases",
        configPath(configId),
      );
      if (result.error) throw new Error("Falha ao carregar casos");
      return result.data!;
    },
  });
}

export function useEvalRuns(configId: string) {
  return useQuery({
    queryKey: ["eval-runs", configId],
    queryFn: async () => {
      const result = await client.GET(
        "/api/v1/configs/{config_id}/eval-runs",
        configPath(configId),
      );
      if (result.error) throw new Error("Falha ao carregar execuções");
      return result.data!;
    },
    // acompanha a execução em background até terminar
    refetchInterval: (query) => (query.state.data?.some(runActive) ? 2_000 : false),
  });
}

export function useEvalRun(configId: string, runId: string | null) {
  return useQuery({
    queryKey: ["eval-run", configId, runId],
    enabled: runId !== null,
    queryFn: async () => {
      const result = await client.GET("/api/v1/configs/{config_id}/eval-runs/{run_id}", {
        params: { path: { config_id: configId, run_id: runId! } },
      });
      if (result.error) throw new Error("Falha ao carregar resultado");
      return result.data!;
    },
    // pelo status do próprio detalhe: a lista pode ver "concluída" antes e parar de consultar
    refetchInterval: (query) => (!query.state.data || runActive(query.state.data) ? 2_000 : false),
  });
}

export function useEvalSettings(configId: string, enabled = true) {
  return useQuery({
    queryKey: ["eval-settings", configId],
    enabled,
    queryFn: async () => {
      const result = await client.GET(
        "/api/v1/configs/{config_id}/eval-settings",
        configPath(configId),
      );
      if (result.error) throw new Error("Falha ao carregar configuração da suíte");
      return result.data!;
    },
  });
}

// caso montado de uma conversa real; nada é gravado até salvar pelo formulário
export function useEvalSuggestion(configId: string, runId: string | null) {
  return useQuery({
    queryKey: ["eval-suggestion", configId, runId],
    enabled: runId !== null,
    retry: false,
    queryFn: async () => {
      const result = await client.GET("/api/v1/configs/{config_id}/eval-cases/suggestion", {
        params: { path: { config_id: configId }, query: { run_id: runId! } },
      });
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Não foi possível montar o caso"));
      return result.data!;
    },
  });
}

export function useEvalSchedule(configId: string) {
  return useQuery({
    queryKey: ["eval-schedule", configId],
    queryFn: async () => {
      const result = await client.GET(
        "/api/v1/configs/{config_id}/eval-schedule",
        configPath(configId),
      );
      if (result.error) throw new Error("Falha ao carregar o agendamento");
      // null: suíte sem agendamento
      return result.data ?? null;
    },
  });
}

// estado da suíte de cada config que já rodou, para as listas de agentes e times
export function useSuiteStatus() {
  return useQuery({
    queryKey: ["eval-status"],
    queryFn: async () => {
      const result = await client.GET("/api/v1/eval-status");
      if (result.error) throw new Error("Falha ao carregar o estado das suítes");
      return new Map((result.data ?? []).map((status) => [status.config_id, status]));
    },
  });
}

export function useEvalComparison(configId: string, base: string | null, target: string | null) {
  return useQuery({
    queryKey: ["eval-compare", configId, base, target],
    enabled: base !== null && target !== null && base !== target,
    queryFn: async () => {
      const result = await client.GET("/api/v1/configs/{config_id}/eval-runs/compare", {
        params: { path: { config_id: configId }, query: { base: base!, target: target! } },
      });
      if (result.error) throw new Error("Falha ao comparar execuções");
      return result.data!;
    },
  });
}

export function useEvalMutations(configId: string) {
  const queryClient = useQueryClient();
  const refresh = (...keys: string[]) =>
    keys.forEach((key) => void queryClient.invalidateQueries({ queryKey: [key, configId] }));

  const saveCase = useMutation({
    mutationFn: async ({ id, body }: { id?: string; body: EvalCaseInput }) => {
      const result = id
        ? await client.PUT("/api/v1/configs/{config_id}/eval-cases/{case_id}", {
            params: { path: { config_id: configId, case_id: id } },
            body,
          })
        : await client.POST("/api/v1/configs/{config_id}/eval-cases", {
            ...configPath(configId),
            body,
          });
      if (result.error) throw new Error(apiErrorMessage(result.error, "Falha ao salvar caso"));
      return result.data!;
    },
    onSuccess: () => refresh("eval-cases"),
  });

  const deleteCase = useMutation({
    mutationFn: async (id: string) => {
      const result = await client.DELETE("/api/v1/configs/{config_id}/eval-cases/{case_id}", {
        params: { path: { config_id: configId, case_id: id } },
      });
      if (result.error) throw new Error(apiErrorMessage(result.error, "Falha ao remover caso"));
    },
    onSuccess: () => refresh("eval-cases"),
  });

  const startRun = useMutation({
    mutationFn: async (body: { version_id: string | null; judge_model: string | null }) => {
      const result = await client.POST("/api/v1/configs/{config_id}/eval-runs", {
        ...configPath(configId),
        body,
      });
      if (result.error) throw new Error(apiErrorMessage(result.error, "Falha ao rodar a suíte"));
      return result.data!;
    },
    onSuccess: () => refresh("eval-runs", "eval-settings"),
  });

  const updateSettings = useMutation({
    mutationFn: async (requirePassing: boolean) => {
      const result = await client.PUT("/api/v1/configs/{config_id}/eval-settings", {
        ...configPath(configId),
        body: { require_passing_evals: requirePassing },
      });
      if (result.error) throw new Error(apiErrorMessage(result.error, "Falha ao salvar o gate"));
      return result.data!;
    },
    onSuccess: () => refresh("eval-settings"),
  });

  const saveSchedule = useMutation({
    mutationFn: async (body: EvalScheduleInput) => {
      const result = await client.PUT("/api/v1/configs/{config_id}/eval-schedule", {
        ...configPath(configId),
        body,
      });
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Falha ao salvar o agendamento"));
      return result.data!;
    },
    onSuccess: () => refresh("eval-schedule"),
  });

  const deleteSchedule = useMutation({
    mutationFn: async () => {
      const result = await client.DELETE(
        "/api/v1/configs/{config_id}/eval-schedule",
        configPath(configId),
      );
      if (result.error)
        throw new Error(apiErrorMessage(result.error, "Falha ao remover o agendamento"));
    },
    onSuccess: () => refresh("eval-schedule"),
  });

  return { saveCase, deleteCase, startRun, updateSettings, saveSchedule, deleteSchedule };
}

export type CaseImportReport = components["schemas"]["CaseImportReport"];

// casos por CSV (ADR-0043): com dryRun, só o relatório por linha; sem ele, tudo ou nada
export async function importCases(
  configId: string,
  file: File,
  dryRun: boolean,
): Promise<CaseImportReport> {
  const form = new FormData();
  form.append("file", file);
  const result = await client.POST("/api/v1/configs/{config_id}/eval-cases/import", {
    params: { path: { config_id: configId }, query: { dry_run: dryRun } },
    // o tipo gerado espera o objeto do schema; o corpo real é multipart
    body: form as unknown as never,
    bodySerializer: (body) => body as unknown as FormData,
  });
  if (result.error) {
    // linha com erro volta 422 com o mesmo relatório da prévia
    const report = result.error as unknown as Partial<CaseImportReport>;
    if (Array.isArray(report.rows)) return report as CaseImportReport;
    throw new Error(apiErrorMessage(result.error, "Falha ao importar a planilha"));
  }
  return result.data!;
}

export function exportCasesUrl(configId: string): string {
  return `/api/api/v1/configs/${configId}/eval-cases/export`;
}
