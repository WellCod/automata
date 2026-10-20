import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { workflowUsage } from "@/components/runs-panel";
import { WorkflowTestPanel } from "@/components/workflow-test-panel";
import type { SseEvent } from "@/lib/sse";
import { applyEvent, EMPTY_PROGRESS, type WorkflowProgress } from "@/lib/workflow-progress";

const ev = (event: string, data: Record<string, unknown> = {}): SseEvent => ({ event, data });

const run = (events: SseEvent[]): WorkflowProgress => events.reduce(applyEvent, EMPTY_PROGRESS);

// sequência real capturada do AgentOS (sem os eventos de modelo e conteúdo)
const atendimento = [
  ev("WorkflowStarted", { session_id: "s1" }),
  ev("StepStarted", { step_name: "triagem" }),
  ev("RunStarted", { step_name: "triagem", agent_name: "Triagem" }),
  ev("StepCompleted", { step_name: "triagem", content: "pedido de reembolso" }),
  ev("ParallelExecutionStarted", { step_name: "análises", parallel_step_count: 2 }),
  ev("StepStarted", { step_name: "técnica" }),
  ev("RunStarted", { step_name: "técnica", agent_name: "Técnico" }),
  ev("StepCompleted", { step_name: "técnica", content: "ok" }),
  ev("StepStarted", { step_name: "financeira" }),
  ev("StepCompleted", { step_name: "financeira", content: "ok" }),
  ev("ParallelExecutionCompleted", { step_name: "análises" }),
  ev("ConditionExecutionStarted", { step_name: "se reembolso", condition_result: false }),
  ev("ConditionExecutionCompleted", {
    step_name: "se reembolso",
    condition_result: false,
    executed_steps: 0,
  }),
  ev("WorkflowCompleted", { content: "resposta final" }),
];

describe("applyEvent", () => {
  it("monta etapas, paralelo indentado e condição que pulou", () => {
    const p = run(atendimento);
    expect(p.status).toBe("done");
    expect(p.final).toBe("resposta final");
    expect(p.sessionId).toBe("s1");
    expect(p.steps.map((s) => [s.name, s.kind, s.status, s.depth])).toEqual([
      ["triagem", "step", "done", 0],
      ["análises", "parallel", "done", 0],
      ["técnica", "step", "done", 1],
      ["financeira", "step", "done", 1],
      ["se reembolso", "condition", "done", 0],
    ]);
    expect(p.steps[0]).toMatchObject({ who: "Triagem", output: "pedido de reembolso" });
    expect(p.steps[1].detail).toBe("2 ramos ao mesmo tempo");
    expect(p.steps[4].detail).toBe("regra falsa: pulou");
  });

  it("repetição mostra a volta e cada volta vira uma entrada", () => {
    const p = run([
      ev("LoopExecutionStarted", { step_name: "até pronto" }),
      ev("LoopIterationStarted", { step_name: "até pronto", iteration: 1, max_iterations: 3 }),
      ev("StepStarted", { step_name: "revisa" }),
      ev("StepCompleted", { step_name: "revisa", content: "ainda não" }),
      ev("LoopIterationStarted", { step_name: "até pronto", iteration: 2, max_iterations: 3 }),
    ]);
    expect(p.steps[0].detail).toBe("volta 2 de 3");
    const after = [
      ev("StepStarted", { step_name: "revisa" }),
      ev("StepCompleted", { step_name: "revisa", content: "pronto" }),
      ev("LoopExecutionCompleted", { step_name: "até pronto", total_iterations: 2 }),
    ].reduce(applyEvent, p);
    expect(after.steps.map((s) => [s.name, s.depth, s.output ?? s.detail])).toEqual([
      ["até pronto", 0, "2 volta(s)"],
      ["revisa", 1, "ainda não"],
      ["revisa", 1, "pronto"],
    ]);
  });

  it("erro na etapa para o fluxo e bloqueio de guardrail aparece à parte", () => {
    const erro = run([
      ev("WorkflowStarted"),
      ev("StepStarted", { step_name: "triagem" }),
      ev("RunError", { step_name: "triagem", content: "provedor fora do ar" }),
      ev("WorkflowError", { error: "etapa triagem falhou" }),
    ]);
    expect(erro.status).toBe("error");
    expect(erro.error).toBe("etapa triagem falhou");
    expect(erro.steps[0]).toMatchObject({ status: "error", detail: "provedor fora do ar" });

    const bloqueio = run([
      ev("StepStarted", { step_name: "triagem" }),
      ev("RunError", {
        step_name: "triagem",
        error_type: "input_check_error",
        additional_data: { rule: "pii_detected" },
        content: "Não posso tratar CPF.",
      }),
      ev("StepCompleted", { step_name: "triagem", content: "Não posso tratar CPF." }),
    ]);
    expect(bloqueio.steps[0]).toMatchObject({ status: "blocked", detail: "pii_detected" });
  });
});

function sse(events: SseEvent[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(c) {
      events.forEach((e) =>
        c.enqueue(enc.encode(`event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)),
      );
      c.close();
    },
  });
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("WorkflowTestPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("roda o rascunho e mostra progresso, resposta final e sessão no run seguinte", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async () => new Response(sse(atendimento)));
    const user = userEvent.setup();
    render(<WorkflowTestPanel workflowId="wf1" draftVersionId="v9" />, { wrapper });

    await user.click(screen.getByLabelText("Testar rascunho"));
    await user.type(screen.getByLabelText("Mensagem para o workflow"), "quero reembolso");
    await user.click(screen.getByRole("button", { name: "Rodar" }));

    expect(await screen.findByText("resposta final")).toBeInTheDocument();
    expect(screen.getByRole("listitem", { name: "triagem: concluída" })).toBeInTheDocument();
    expect(screen.getByText("regra falsa: pulou")).toBeInTheDocument();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/workflows/wf1/runs");
    const body = (init as RequestInit).body as FormData;
    expect(body.get("factory_input")).toBe(JSON.stringify({ version_id: "v9" }));
    expect(body.get("session_id")).toBeNull();

    await user.type(screen.getByLabelText("Mensagem para o workflow"), "e agora?");
    await user.click(screen.getByRole("button", { name: "Rodar" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(((fetchMock.mock.calls[1][1] as RequestInit).body as FormData).get("session_id")).toBe(
      "s1",
    );
  });

  it("falha do workflow aparece como alerta", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      async () =>
        new Response(
          sse([
            ev("StepStarted", { step_name: "triagem" }),
            ev("WorkflowError", { error: "provedor fora do ar" }),
          ]),
        ),
    );
    const user = userEvent.setup();
    render(<WorkflowTestPanel workflowId="wf1" />, { wrapper });
    await user.type(screen.getByLabelText("Mensagem para o workflow"), "oi");
    await user.click(screen.getByRole("button", { name: "Rodar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("provedor fora do ar");
    expect(screen.getByRole("listitem", { name: "triagem: falhou" })).toBeInTheDocument();
  });
});

describe("workflowUsage", () => {
  it("resume etapas, tokens e custo somados", () => {
    const base = {
      id: "r",
      agent_config_id: "c",
      user_id: "u",
      run_id: "x",
      status: "success",
      duration_ms: 10,
      error: null,
      created_at: "2026-10-19T00:00:00Z",
    };
    // Intl separa a moeda com espaço não separável
    const usage = workflowUsage({ ...base, steps: 5, total_tokens: 1234, cost: 0.0021 });
    expect(usage.replace(/\s/g, " ")).toBe("5 etapas · 1.234 tokens · US$ 0,0021");
    expect(workflowUsage({ ...base, steps: 1, total_tokens: 0, cost: null })).toBe(
      "1 etapa · 0 tokens",
    );
  });
});
