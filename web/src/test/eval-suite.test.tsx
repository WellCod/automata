import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvalCaseForm } from "@/components/eval-case-form";
import { EvalSuitePanel } from "@/components/eval-suite-panel";
import { SuiteBadge } from "@/components/suite-badge";
import { availableTypes, caseErrors, type EvalCheck, newCheck } from "@/lib/eval-checks";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("checagens", () => {
  it("um tools e um juiz por caso, texto quantos couberem até 5", () => {
    const one: EvalCheck[] = [newCheck("tools"), newCheck("judge")];
    expect(availableTypes(one)).toEqual(["text"]);
    expect(availableTypes([newCheck("text")])).toEqual(["text", "tools", "judge"]);
    expect(availableTypes(Array.from({ length: 5 }, () => newCheck("text")))).toEqual([]);
  });

  it("acusa o que a API recusaria", () => {
    const base = { name: "prazo", input: "Qual o prazo?" };
    expect(caseErrors({ ...base, checks: [] })).toContain("Adicione ao menos uma checagem.");
    expect(caseErrors({ ...base, checks: [newCheck("text")] })).toContain(
      "Preencha o texto da regra.",
    );
    expect(caseErrors({ ...base, checks: [newCheck("tools")] })).toContain(
      "Liste ao menos uma tool.",
    );
    expect(
      caseErrors({ ...base, checks: [{ type: "text", kind: "not_empty", value: "" }] }),
    ).toEqual([]);
  });
});

describe("EvalCaseForm", () => {
  it("monta o caso com texto, tools e juiz", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<EvalCaseForm saving={false} onSave={onSave} onCancel={() => {}} />);

    await user.type(screen.getByLabelText("Nome do caso"), "prazo de troca");
    await user.type(screen.getByLabelText("Mensagem de entrada"), "Ainda dá para trocar?");
    await user.type(screen.getByLabelText("Texto da checagem 1"), "30 dias");
    await user.click(screen.getByRole("button", { name: "Tools chamadas" }));
    const tools = screen.getByLabelText("Tools da checagem 2");
    await user.type(tools, "buscar_politicas, buscar_politicas");
    fireEvent.blur(tools);
    await user.click(screen.getByRole("button", { name: "Critério do juiz" }));
    expect(screen.queryByRole("button", { name: "Tools chamadas" })).toBeNull();
    await user.type(screen.getByLabelText("Critério da checagem 3"), "Cita a política de troca");
    await user.selectOptions(screen.getByLabelText("Modo do juiz da checagem 3"), "numeric");
    await user.click(screen.getByRole("button", { name: "Salvar caso" }));

    expect(onSave).toHaveBeenCalledWith({
      name: "prazo de troca",
      input: "Ainda dá para trocar?",
      checks: [
        { type: "text", kind: "contains", value: "30 dias" },
        { type: "tools", tools: ["buscar_politicas"], allow_additional: true },
        { type: "judge", criteria: "Cita a política de troca", mode: "numeric", threshold: 7 },
      ],
    });
  });
});

const CASES = [
  {
    id: "c1",
    agent_config_id: "a1",
    name: "prazo",
    input: "Qual o prazo?",
    checks: [{ type: "text", kind: "contains", value: "30 dias" }],
    position: 0,
    updated_by: "u",
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
  {
    id: "c2",
    agent_config_id: "a1",
    name: "tom",
    input: "Oi",
    checks: [
      { type: "judge", criteria: "Responde com cordialidade", mode: "binary", threshold: 7 },
    ],
    position: 1,
    updated_by: "u",
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
];

const run = (id: string, version: string, status: string, extra: object = {}) => ({
  id,
  agent_config_id: "a1",
  version_id: version,
  version_number: version === "v-draft" ? 3 : 2,
  version_status: version === "v-draft" ? "draft" : "published",
  status,
  total: 2,
  passed: 1,
  failed: 1,
  not_evaluated: 0,
  error: null,
  judge_model: "gpt-4o-mini",
  total_tokens: 1234,
  cost: 0.0021,
  started_by: "u",
  trigger: "manual",
  target: null,
  verdict: "failed",
  created_at: "2026-10-20T10:00:00Z",
  started_at: null,
  finished_at: null,
  ...extra,
});

describe("EvalSuitePanel", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      const data: Record<string, unknown> = {
        "/api/v1/configs/{config_id}/eval-cases": CASES,
        "/api/v1/configs/{config_id}/eval-runs": [
          run("r-draft", "v-draft", "completed"),
          run("r-current", "v-current", "completed", { passed: 2, failed: 0 }),
        ],
        "/api/v1/configs/{config_id}/eval-runs/{run_id}": {
          ...run("r-draft", "v-draft", "completed"),
          results: [
            {
              id: "x1",
              case_id: "c1",
              case_name: "prazo",
              position: 0,
              status: "failed",
              checks: [
                {
                  type: "text",
                  passed: false,
                  rules: [{ kind: "contains", value: "30 dias", passed: false }],
                },
              ],
              output: "Não sei informar.",
              tools_called: [],
              duration_ms: 1200,
              error: null,
              session_id: null,
            },
          ],
        },
        "/api/v1/configs/{config_id}/eval-settings": {
          require_passing_evals: true,
          draft_version_id: "v-draft",
          draft_run: null,
          can_publish: false,
          reason: "1 de 2 casos não passaram no rascunho atual",
        },
        "/api/v1/configs/{config_id}/eval-runs/compare": {
          base: run("r-current", "v-current", "completed"),
          target: run("r-draft", "v-draft", "completed"),
          regressions: 1,
          fixes: 0,
          cases: [
            {
              case_id: "c1",
              case_name: "prazo",
              base_status: "passed",
              target_status: "failed",
              change: "regression",
            },
          ],
        },
        "/api/v1/models/capabilities": {
          "gpt-4o-mini": { structured_output: true },
          "sem-schema": { structured_output: false },
        },
      };
      return { data: data[path], error: undefined } as never;
    });
    vi.mocked(client.POST).mockResolvedValue({
      data: run("r-new", "v-draft", "queued"),
      error: undefined,
    } as never);
  });

  it("mostra gate, resultado por caso e a regressão contra a vigente", async () => {
    render(
      <EvalSuitePanel
        configId="a1"
        draftVersion={{ id: "v-draft", version_number: 3 }}
        currentVersion={{ id: "v-current", version_number: 2 }}
      />,
      { wrapper },
    );

    expect(await screen.findByText(/Publicação bloqueada: 1 de 2 casos/)).toBeInTheDocument();
    expect(await screen.findByText(/1 de 2 passaram · 1 falharam/)).toBeInTheDocument();
    const result = screen.getByRole("listitem", { name: "prazo: falhou" });
    expect(within(result).getByText("Não sei informar.")).toBeInTheDocument();
    expect(within(result).getByText(/✗ contains "30 dias"/)).toBeInTheDocument();

    const compared = await screen.findByRole("list", { name: "Casos comparados" });
    expect(within(compared).getByText("regressão")).toBeInTheDocument();
    expect(screen.getByText(/1 regressão\(ões\) · 0 corrigido\(s\)/)).toBeInTheDocument();
  });

  it("roda o rascunho com o juiz escolhido entre os modelos com saída estruturada", async () => {
    const user = userEvent.setup();
    render(
      <EvalSuitePanel
        configId="a1"
        draftVersion={{ id: "v-draft", version_number: 3 }}
        currentVersion={{ id: "v-current", version_number: 2 }}
      />,
      { wrapper },
    );
    const judge = await screen.findByLabelText("Modelo do juiz");
    await within(judge).findByRole("option", { name: "gpt-4o-mini" });
    expect(within(judge).queryByRole("option", { name: "sem-schema" })).toBeNull();
    await user.selectOptions(judge, "gpt-4o-mini");
    await user.click(screen.getByRole("button", { name: "Rodar suíte" }));

    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/configs/{config_id}/eval-runs", {
        params: { path: { config_id: "a1" } },
        body: { version_id: "v-draft", judge_model: "gpt-4o-mini" },
      }),
    );
  });

  it("agenda a suíte e marca as execuções agendadas", async () => {
    vi.mocked(client.PUT).mockResolvedValue({
      data: {
        agent_config_id: "a1",
        cron_expr: "0 8 * * 1-5",
        timezone: "America/Sao_Paulo",
        target: "current",
        judge_model: "gpt-4o-mini",
        enabled: true,
        next_run_at: "2026-10-22T11:00:00Z",
        last_attempt_at: null,
        last_run_id: null,
        last_error: null,
        updated_by: "u",
        updated_at: "2026-10-21T10:00:00Z",
      },
      error: undefined,
    } as never);
    const base = vi.mocked(client.GET).getMockImplementation()!;
    vi.mocked(client.GET).mockImplementation(async (path: string, opts?: unknown) => {
      if (path === "/api/v1/configs/{config_id}/eval-schedule")
        return { data: undefined, error: { detail: "x" }, response: { status: 404 } } as never;
      if (path === "/api/v1/configs/{config_id}/eval-runs")
        return {
          data: [run("r-sched", "v-current", "completed", { trigger: "schedule" })],
          error: undefined,
        } as never;
      return (base as (...args: unknown[]) => Promise<never>)(path, opts);
    });
    const user = userEvent.setup();
    render(
      <EvalSuitePanel
        configId="a1"
        draftVersion={{ id: "v-draft", version_number: 3 }}
        currentVersion={{ id: "v-current", version_number: 2 }}
      />,
      { wrapper },
    );

    expect(
      await screen.findByRole("option", { name: /v2 \(publicada\).*agendada/ }),
    ).toBeInTheDocument();
    const section = await screen.findByRole("region", { name: "Agendamento" });
    expect(within(section).getByText(/custa por volta de/)).toBeInTheDocument();
    await user.selectOptions(within(section).getByLabelText("Frequência"), "0 8 * * 1-5");
    await user.selectOptions(
      within(section).getByLabelText("Modelo do juiz no agendamento"),
      "gpt-4o-mini",
    );
    await user.click(within(section).getByRole("button", { name: "Agendar" }));

    await waitFor(() =>
      expect(client.PUT).toHaveBeenCalledWith("/api/v1/configs/{config_id}/eval-schedule", {
        params: { path: { config_id: "a1" } },
        body: {
          cron_expr: "0 8 * * 1-5",
          timezone: "America/Sao_Paulo",
          target: "current",
          judge_model: "gpt-4o-mini",
          enabled: true,
        },
      }),
    );
  });
});

describe("SuiteBadge", () => {
  it("mostra regressão com a contagem desde o último agendado", () => {
    render(
      <SuiteBadge
        status={{
          config_id: "a1",
          state: "regressed",
          regressions: 2,
          previous_run_id: "r0",
          last_run: run("r1", "v-current", "completed", { trigger: "schedule" }) as never,
        }}
      />,
    );
    expect(screen.getByText("Suíte regrediu (2 desde o último agendado)")).toBeInTheDocument();
  });
});
