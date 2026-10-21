"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import client from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/errors";
import { type EvalCaseInput, type EvalScheduleInput, runActive } from "@/lib/eval-checks";

const path = (configId: string) => ({ params: { path: { config_id: configId } } });

export function useEvalCases(configId: string, enabled = true) {
  return useQuery({
    queryKey: ["eval-cases", configId],
    enabled,
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/eval-cases", path(configId));
      if (res.error) throw new Error("Falha ao carregar casos");
      return res.data!;
    },
  });
}

export function useEvalRuns(configId: string) {
  return useQuery({
    queryKey: ["eval-runs", configId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/eval-runs", path(configId));
      if (res.error) throw new Error("Falha ao carregar execuções");
      return res.data!;
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
      const res = await client.GET("/api/v1/configs/{config_id}/eval-runs/{run_id}", {
        params: { path: { config_id: configId, run_id: runId! } },
      });
      if (res.error) throw new Error("Falha ao carregar resultado");
      return res.data!;
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
      const res = await client.GET("/api/v1/configs/{config_id}/eval-settings", path(configId));
      if (res.error) throw new Error("Falha ao carregar configuração da suíte");
      return res.data!;
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
      const res = await client.GET("/api/v1/configs/{config_id}/eval-cases/suggestion", {
        params: { path: { config_id: configId }, query: { run_id: runId! } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Não foi possível montar o caso"));
      return res.data!;
    },
  });
}

export function useEvalSchedule(configId: string) {
  return useQuery({
    queryKey: ["eval-schedule", configId],
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/eval-schedule", path(configId));
      if (res.error) {
        // suíte sem agendamento responde 404
        if (res.response?.status === 404) return null;
        throw new Error("Falha ao carregar o agendamento");
      }
      return res.data ?? null;
    },
  });
}

// estado da suíte de cada config que já rodou, para as listas de agentes e times
export function useSuiteStatus() {
  return useQuery({
    queryKey: ["eval-status"],
    queryFn: async () => {
      const res = await client.GET("/api/v1/eval-status");
      if (res.error) throw new Error("Falha ao carregar o estado das suítes");
      return new Map((res.data ?? []).map((s) => [s.config_id, s]));
    },
  });
}

export function useEvalComparison(configId: string, base: string | null, target: string | null) {
  return useQuery({
    queryKey: ["eval-compare", configId, base, target],
    enabled: base !== null && target !== null && base !== target,
    queryFn: async () => {
      const res = await client.GET("/api/v1/configs/{config_id}/eval-runs/compare", {
        params: { path: { config_id: configId }, query: { base: base!, target: target! } },
      });
      if (res.error) throw new Error("Falha ao comparar execuções");
      return res.data!;
    },
  });
}

export function useEvalMutations(configId: string) {
  const queryClient = useQueryClient();
  const refresh = (...keys: string[]) =>
    keys.forEach((k) => void queryClient.invalidateQueries({ queryKey: [k, configId] }));

  const saveCase = useMutation({
    mutationFn: async ({ id, body }: { id?: string; body: EvalCaseInput }) => {
      const res = id
        ? await client.PUT("/api/v1/configs/{config_id}/eval-cases/{case_id}", {
            params: { path: { config_id: configId, case_id: id } },
            body,
          })
        : await client.POST("/api/v1/configs/{config_id}/eval-cases", {
            ...path(configId),
            body,
          });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar caso"));
      return res.data!;
    },
    onSuccess: () => refresh("eval-cases"),
  });

  const deleteCase = useMutation({
    mutationFn: async (id: string) => {
      const res = await client.DELETE("/api/v1/configs/{config_id}/eval-cases/{case_id}", {
        params: { path: { config_id: configId, case_id: id } },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover caso"));
    },
    onSuccess: () => refresh("eval-cases"),
  });

  const startRun = useMutation({
    mutationFn: async (body: { version_id: string | null; judge_model: string | null }) => {
      const res = await client.POST("/api/v1/configs/{config_id}/eval-runs", {
        ...path(configId),
        body,
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao rodar a suíte"));
      return res.data!;
    },
    onSuccess: () => refresh("eval-runs", "eval-settings"),
  });

  const updateSettings = useMutation({
    mutationFn: async (require: boolean) => {
      const res = await client.PUT("/api/v1/configs/{config_id}/eval-settings", {
        ...path(configId),
        body: { require_passing_evals: require },
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o gate"));
      return res.data!;
    },
    onSuccess: () => refresh("eval-settings"),
  });

  const saveSchedule = useMutation({
    mutationFn: async (body: EvalScheduleInput) => {
      const res = await client.PUT("/api/v1/configs/{config_id}/eval-schedule", {
        ...path(configId),
        body,
      });
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao salvar o agendamento"));
      return res.data!;
    },
    onSuccess: () => refresh("eval-schedule"),
  });

  const deleteSchedule = useMutation({
    mutationFn: async () => {
      const res = await client.DELETE("/api/v1/configs/{config_id}/eval-schedule", path(configId));
      if (res.error) throw new Error(apiErrorMessage(res.error, "Falha ao remover o agendamento"));
    },
    onSuccess: () => refresh("eval-schedule"),
  });

  return { saveCase, deleteCase, startRun, updateSettings, saveSchedule, deleteSchedule };
}
