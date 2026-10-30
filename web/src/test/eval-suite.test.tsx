import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvalCaseForm } from "@/components/eval-case-form";
import { EvalSuitePanel } from "@/components/eval-suite-panel";
import { EvalWebhook } from "@/components/eval-webhook";
import { RunsPanel } from "@/components/runs-panel";
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
    expect(availableTypes(one)).toEqual(["text", "schema"]);
    expect(availableTypes([newCheck("text")])).toEqual(["text", "tools", "judge", "schema"]);
    expect(availableTypes(Array.from({ length: 5 }, () => newCheck("text")))).toEqual([]);
  });

  it("workflow troca tools e bloqueio por etapas", () => {
    expect(availableTypes([], "workflow")).toEqual(["text", "judge", "steps"]);
    expect(availableTypes([newCheck("steps")], "workflow")).toEqual(["text", "judge"]);
    expect(availableTypes([], "team")).not.toContain("steps");
    const base = { name: "caminho", input: "Quero reembolso" };
    expect(caseErrors({ ...base, checks: [newCheck("steps")] })).toContain(
      "Liste ao menos uma etapa.",
    );
  });

  it("bloqueio só entra em caso sem outra checagem", () => {
    expect(availableTypes([])).toEqual(["text", "tools", "judge", "blocked", "schema"]);
    expect(availableTypes([newCheck("text")])).not.toContain("blocked");
    expect(availableTypes([newCheck("blocked")])).toEqual([]);
    const base = { name: "frete", input: "E o frete?" };
    expect(caseErrors({ ...base, checks: [newCheck("blocked"), newCheck("judge")] })).toContain(
      "Caso que espera bloqueio não leva outras checagens.",
    );
    expect(caseErrors({ ...base, checks: [{ type: "blocked", rule: "off_topic" }] })).toEqual([]);
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
  it("caso de workflow confere as etapas e não tem conversa anterior", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<EvalCaseForm kind="workflow" saving={false} onSave={onSave} onCancel={() => {}} />);

    expect(screen.queryByText("Conversa antes da mensagem (opcional)")).toBeNull();
    expect(screen.queryByRole("button", { name: "Tools chamadas" })).toBeNull();
    await user.type(screen.getByLabelText("Nome do caso"), "reembolso revisa");
    await user.type(screen.getByLabelText("Mensagem de entrada"), "Quero reembolso");
    await user.click(screen.getByRole("button", { name: "Remover checagem 1" }));
    await user.click(screen.getByRole("button", { name: "Etapas que rodaram" }));
    const steps = screen.getByLabelText("Etapas da checagem 1");
    await user.type(steps, "triagem, revisao, triagem");
    fireEvent.blur(steps);
    await user.click(screen.getByLabelText("Reprovar se rodar outras etapas além destas"));
    await user.click(screen.getByRole("button", { name: "Salvar caso" }));

    expect(onSave).toHaveBeenCalledWith({
      name: "reembolso revisa",
      input: "Quero reembolso",
      checks: [{ type: "steps", steps: ["triagem", "revisao"], exclusive: true }],
    });
  });

  it("monta o caso que espera bloqueio com a regra", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    render(<EvalCaseForm saving={false} onSave={onSave} onCancel={() => {}} />);

    await user.type(screen.getByLabelText("Nome do caso"), "barra frete");
    await user.type(screen.getByLabelText("Mensagem de entrada"), "Quanto custa o frete?");
    await user.click(screen.getByRole("button", { name: "Remover checagem 1" }));
    await user.click(screen.getByRole("button", { name: "Bloqueio do guardrail" }));
    await user.selectOptions(screen.getByLabelText("Regra do bloqueio da checagem 1"), "off_topic");
    // com bloqueio, nenhuma outra checagem cabe
    expect(screen.queryByRole("button", { name: "Texto da resposta" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Salvar caso" }));

    expect(onSave).toHaveBeenCalledWith({
      name: "barra frete",
      input: "Quanto custa o frete?",
      checks: [{ type: "blocked", rule: "off_topic" }],
    });
  });

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

describe("virar caso de teste", () => {
  it("o histórico oferece o caso para run de conversa e não para bloqueado", async () => {
    const item = (id: string, status: string) => ({
      id,
      agent_config_id: "a1",
      user_id: "u",
      run_id: `run-${id}`,
      session_id: "s1",
      status,
      duration_ms: 900,
      error: null,
      blocked_by: null,
      created_at: "2026-10-21T10:00:00Z",
    });
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if (path === "/api/v1/configs/{config_id}/runs")
        return {
          data: { items: [item("1", "success"), item("2", "blocked")], total: 2 },
          error: undefined,
        } as never;
      return { data: undefined, error: undefined } as never;
    });
    const onMakeCase = vi.fn();
    const user = userEvent.setup();
    render(<RunsPanel agentId="a1" onMakeCase={onMakeCase} />, { wrapper });

    const [ok, blocked] = await screen.findAllByRole("button", { expanded: false });
    await user.click(blocked!);
    expect(screen.queryByRole("button", { name: "Virar caso de teste" })).toBeNull();
    await user.click(ok!);
    await user.click(await screen.findByRole("button", { name: "Virar caso de teste" }));
    expect(onMakeCase).toHaveBeenCalledWith("run-1");
  });

  it("abre o caso preenchido com contexto, avisos e critério sugerido", async () => {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      const data: Record<string, unknown> = {
        "/api/v1/configs/{config_id}/eval-cases": [],
        "/api/v1/configs/{config_id}/eval-runs": [],
        "/api/v1/configs/{config_id}/eval-cases/suggestion": {
          name: "meu CPF é [CPF removido]",
          input: "meu CPF é [CPF removido]",
          context: ["oi, preciso trocar um produto"],
          checks: [{ type: "text", kind: "not_empty", value: "" }],
          judge_criteria: "Responde com o mesmo conteúdo essencial desta resposta de referência",
          source_run_id: "run-1",
          notes: ["Dados pessoais foram mascarados."],
        },
      };
      return { data: data[path], error: undefined } as never;
    });
    vi.mocked(client.POST).mockResolvedValue({ data: {}, error: undefined } as never);
    const onDone = vi.fn();
    const user = userEvent.setup();
    render(<EvalSuitePanel configId="a1" fromRun="run-1" onFromRunDone={onDone} />, {
      wrapper,
    });

    const form = await screen.findByRole("form", { name: "Caso da conversa" });
    expect(within(form).getByText("Dados pessoais foram mascarados.")).toBeInTheDocument();
    expect(within(form).getByLabelText("Mensagem anterior 1")).toHaveValue(
      "oi, preciso trocar um produto",
    );
    await user.click(
      within(form).getByRole("button", { name: "Critério sugerido pela resposta original" }),
    );
    await user.click(within(form).getByRole("button", { name: "Salvar caso" }));

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    expect(vi.mocked(client.POST).mock.calls.at(-1)![1]).toMatchObject({
      body: {
        input: "meu CPF é [CPF removido]",
        context: ["oi, preciso trocar um produto"],
        source_run_id: "run-1",
        checks: [
          { type: "text", kind: "not_empty" },
          { type: "judge", mode: "binary", threshold: 7 },
        ],
      },
    });
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });
});

describe("EvalWebhook", () => {
  const schedule = {
    agent_config_id: "a1",
    cron_expr: "0 8 * * *",
    timezone: "America/Sao_Paulo",
    target: "current",
    judge_model: null,
    enabled: true,
    next_run_at: null,
    last_attempt_at: null,
    last_run_id: null,
    last_error: null,
    webhook_host: null,
    webhook_last_status: null,
    webhook_last_at: null,
    updated_by: "u",
    updated_at: "2026-10-21T10:00:00Z",
  } as const;

  it("mostra o segredo uma vez e testa o webhook cadastrado", async () => {
    vi.mocked(client.PUT).mockResolvedValue({
      data: { host: "hooks.slack.com", secret: "segredo-uma-vez" },
      error: undefined,
    } as never);
    vi.mocked(client.POST).mockResolvedValue({
      data: { status: "HTTP 200", delivered: true },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    const { rerender } = render(<EvalWebhook configId="a1" schedule={schedule} />, { wrapper });

    await user.type(screen.getByLabelText("URL do webhook"), "https://hooks.slack.com/services/x");
    await user.click(screen.getByRole("button", { name: "Salvar webhook" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Segredo do webhook" });
    expect(dialog).toHaveTextContent("segredo-uma-vez");
    expect(vi.mocked(client.PUT).mock.calls.at(-1)![1]).toMatchObject({
      body: { url: "https://hooks.slack.com/services/x" },
    });
    await user.click(screen.getByRole("button", { name: "Já guardei" }));
    expect(screen.queryByText("segredo-uma-vez")).toBeNull();

    rerender(
      <EvalWebhook
        configId="a1"
        schedule={{ ...schedule, webhook_host: "hooks.slack.com", webhook_last_status: "HTTP 410" }}
      />,
    );
    expect(screen.getByText("hooks.slack.com")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Último envio: HTTP 410");
    await user.click(screen.getByRole("button", { name: "Enviar teste" }));
    await waitFor(() =>
      expect(vi.mocked(client.POST).mock.calls.at(-1)![0]).toBe(
        "/api/v1/configs/{config_id}/eval-schedule/webhook/test",
      ),
    );
  });
});
