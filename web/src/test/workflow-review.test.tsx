import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ApprovalsPage from "@/app/aprovacoes/page";
import { applyContinue, applyEvent, EMPTY_PROGRESS } from "@/lib/workflow-progress";
import { structureErrors, type WorkflowNode } from "@/lib/workflow-tree";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const step = (name: string, review?: object): WorkflowNode =>
  ({
    type: "step",
    name,
    agent_id: "a1",
    on_error: "stop",
    max_retries: 0,
    ...(review ? { review } : {}),
  }) as WorkflowNode;

describe("revisão na estrutura", () => {
  it("só no nível principal", () => {
    const review = { when: "after", on_reject: "cancel" };
    expect(structureErrors([step("analise", review), step("fim")])).toEqual([]);
    const inCondition: WorkflowNode = {
      type: "condition",
      name: "se",
      rule: { kind: "contains", source: "input", value: "x" },
      steps: [step("dentro", review)],
      else_steps: [],
    };
    expect(structureErrors([inCondition, step("fim")])).toContain(
      '"dentro" está dentro de um contêiner: revisão humana só no nível principal.',
    );
    const inLoop: WorkflowNode = {
      type: "loop",
      name: "voltas",
      steps: [step("volta", review)],
      max_iterations: 3,
      until: null,
    };
    expect(structureErrors([inLoop])).toContain(
      '"volta" está dentro de um contêiner: revisão humana só no nível principal.',
    );
  });
});

describe("progresso com pausa", () => {
  const requirement = {
    step_id: "s1",
    step_name: "analise",
    requires_output_review: true,
    output_review_message: "Confira o valor",
    step_output: { content: "reembolso de R$ 120" },
  };

  it("WorkflowPaused traz a etapa e a saída para aprovar", () => {
    let p = applyEvent(EMPTY_PROGRESS, {
      event: "WorkflowStarted",
      data: { run_id: "r1", session_id: "s" },
    });
    p = applyEvent(p, { event: "WorkflowPaused", data: { step_requirements: [requirement] } });
    expect(p.status).toBe("paused");
    expect(p.runId).toBe("r1");
    expect(p.pending).toEqual({
      stepName: "analise",
      when: "after",
      message: "Confira o valor",
      output: "reembolso de R$ 120",
    });
  });

  it("continue fecha, pausa de novo ou encerra", () => {
    const paused = { ...EMPTY_PROGRESS, status: "paused" as const, runId: "r1" };
    expect(applyContinue(paused, { status: "COMPLETED", content: "feito" })).toMatchObject({
      status: "done",
      final: "feito",
      pending: null,
    });
    expect(
      applyContinue(paused, {
        status: "PAUSED",
        step_requirements: [{ ...requirement, confirmed: false }, requirement],
      }).pending?.stepName,
    ).toBe("analise");
    expect(applyContinue(paused, { status: "CANCELLED" })).toMatchObject({
      status: "error",
      error: "Revisão recusada: workflow encerrado.",
    });
  });
});

describe("Aprovações com etapa de workflow", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal("fetch", fetchMock);
    vi.mocked(client.GET).mockResolvedValue({
      data: [
        {
          run_id: "r1",
          agent_id: "w1",
          agent_name: "Reembolso",
          kind: "workflow",
          session_id: "s1",
          user_id: "ana",
          created_at: "2026-10-21T10:00:00Z",
          tools: [],
          steps: [
            {
              step_id: "st1",
              step_name: "analise",
              when: "after",
              message: "Confira o valor",
              output: "reembolso de R$ 120",
              timeout_at: null,
              retry_count: 0,
            },
          ],
        },
      ],
      error: undefined,
    } as never);
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith("/continue")) return new Response(JSON.stringify({ status: "COMPLETED" }));
      return new Response(
        JSON.stringify({
          step_requirements: [
            { step_id: "old", confirmed: true },
            { step_id: "st1", requires_output_review: true },
          ],
        }),
      );
    });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("mostra a saída e recusa com motivo pelo continue do AgentOS", async () => {
    const user = userEvent.setup();
    render(<ApprovalsPage />, { wrapper });
    expect(await screen.findByText("reembolso de R$ 120")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Reembolso" })).toHaveAttribute(
      "href",
      "/workflows/w1",
    );
    await user.type(screen.getByLabelText("Motivo da recusa"), "faltou o pedido");
    await user.click(screen.getByRole("button", { name: "Recusar" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[0][0]).toBe("/api/workflows/w1/runs/r1?session_id=s1");
    const [url, init] = fetchMock.mock.calls[1] as [string, { body: FormData }];
    expect(url).toBe("/api/workflows/w1/runs/r1/continue");
    const sent = JSON.parse(String(init.body.get("step_requirements")));
    // a lista volta inteira, com só o último decidido
    expect(sent).toEqual([
      { step_id: "old", confirmed: true },
      {
        step_id: "st1",
        requires_output_review: true,
        confirmed: false,
        rejection_feedback: "faltou o pedido",
      },
    ]);
    expect(init.body.get("session_id")).toBe("s1");
  });
});
