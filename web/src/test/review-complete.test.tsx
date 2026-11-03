import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ReviewHistory } from "@/components/review-history";
import { StepReviewActions } from "@/components/step-review-actions";
import { decideWorkflowStep, type StepDecision } from "@/lib/api/approvals";
import { diffLines } from "@/lib/text-diff";
import { pendingFrom } from "@/lib/workflow-progress";
import { loopReviewErrors, type WorkflowNode } from "@/lib/workflow-tree";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("diff da edição", () => {
  it("marca o que saiu e o que entrou, linha a linha", () => {
    expect(diffLines("pedido 1\nvalor R$ 120\nok", "pedido 1\nvalor R$ 210\nok")).toEqual([
      { kind: "same", text: "pedido 1" },
      { kind: "removed", text: "valor R$ 120" },
      { kind: "added", text: "valor R$ 210" },
      { kind: "same", text: "ok" },
    ]);
  });

  it("texto enorme não trava o navegador", () => {
    const big = Array.from({ length: 1000 }, (_, i) => `linha ${i}`).join("\n");
    expect(diffLines(big, `${big}\nmais`)).toBeNull();
  });
});

describe("decisão na pausa", () => {
  it("edita a saída, mostra o diff e aprova com a edição", async () => {
    const decisions: StepDecision[] = [];
    const user = userEvent.setup();
    render(
      <StepReviewActions
        when="after"
        output="reembolso de R$ 120"
        busy={false}
        onDecide={(d) => decisions.push(d)}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Editar saída" }));
    const approve = screen.getByRole("button", { name: "Aprovar com a edição" });
    expect(approve).toBeDisabled();
    const editor = screen.getByLabelText(/Saída editada/);
    await user.clear(editor);
    await user.type(editor, "reembolso de R$ 210");
    expect(screen.getByLabelText("Diferença da edição")).toHaveTextContent("R$ 210");
    await user.click(approve);
    expect(decisions).toEqual([{ approve: true, edited: "reembolso de R$ 210" }]);
  });

  it("confirmação antes de rodar não oferece edição", () => {
    render(<StepReviewActions when="before" busy={false} onDecide={() => {}} />);
    expect(screen.queryByRole("button", { name: "Editar saída" })).toBeNull();
  });

  it("volta de laço segue ou pede outra só com comentário", async () => {
    const decisions: StepDecision[] = [];
    const user = userEvent.setup();
    render(
      <StepReviewActions
        when="loop"
        output="rascunho 1"
        busy={false}
        onDecide={(d) => decisions.push(d)}
      />,
    );
    const again = screen.getByRole("button", { name: "Pedir outra volta" });
    expect(again).toBeDisabled();
    await user.type(screen.getByLabelText("Comentário para a próxima volta"), "mais curto");
    await user.click(again);
    await user.click(screen.getByRole("button", { name: "Seguir com esta volta" }));
    expect(decisions).toEqual([{ approve: false, feedback: "mais curto" }, { approve: true }]);
  });
});

describe("continue com a edição", () => {
  const fetchMock = vi.fn();
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => vi.unstubAllGlobals());

  it("manda edited_output no requisito ativo", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith("/continue")) return new Response(JSON.stringify({ status: "COMPLETED" }));
      return new Response(
        JSON.stringify({ step_requirements: [{ step_id: "s1", requires_output_review: true }] }),
      );
    });
    await decideWorkflowStep("w1", "r1", "sess", { approve: true, edited: "novo texto" });
    const init = fetchMock.mock.calls[1][1] as { body: FormData };
    expect(JSON.parse(String(init.body.get("step_requirements")))).toEqual([
      { step_id: "s1", requires_output_review: true, confirmed: true, edited_output: "novo texto" },
    ]);
  });
});

describe("laço com revisão", () => {
  it("o modo teste reconhece a pausa da volta", () => {
    const pending = pendingFrom([
      {
        step_name: "rascunhos",
        step_type: "Loop",
        requires_output_review: true,
        output_review_message: "Ficou bom?",
        step_output: { content: "rascunho 1" },
      },
    ]);
    expect(pending).toEqual({
      stepName: "rascunhos",
      when: "loop",
      message: "Ficou bom?",
      output: "rascunho 1",
    });
  });

  it("só no nível principal e com uma etapa", () => {
    const step = (name: string) =>
      ({ type: "step", name, agent_id: "a", on_error: "stop", max_retries: 0 }) as WorkflowNode;
    const loop = (steps: WorkflowNode[]) =>
      ({
        type: "loop",
        name: "voltas",
        steps,
        max_iterations: 3,
        until: null,
        review: { message: "", timeout_hours: null },
      }) as WorkflowNode;
    expect(loopReviewErrors([loop([step("a")])])).toEqual([]);
    expect(loopReviewErrors([loop([step("a"), step("b")])])[0]).toContain("uma etapa só");
    const nested: WorkflowNode = {
      type: "condition",
      name: "se",
      rule: { kind: "always", source: "input", value: "" },
      steps: [loop([step("a")])],
      else_steps: [],
    };
    expect(loopReviewErrors([nested])[0]).toContain("nível principal");
  });
});

describe("histórico das decisões", () => {
  it("lista quem decidiu e abre a edição", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [
        {
          step_id: "s1",
          step_name: "analise",
          decision: "rejected",
          by: "ana",
          at: "2026-10-30T10:00:00Z",
          feedback: "faltou o valor",
        },
        {
          step_id: "s1",
          step_name: "analise",
          decision: "edited",
          by: "ana",
          at: "2026-10-30T10:05:00Z",
          before: "R$ 120",
          after: "R$ 210",
        },
      ],
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<ReviewHistory runId="r1" />, { wrapper });
    const history = await screen.findByRole("region", { name: "Decisões humanas" });
    expect(history).toHaveTextContent("ana recusou analise");
    expect(history).toHaveTextContent("“faltou o valor”");
    await user.click(screen.getByRole("button", { name: "Ver a edição" }));
    expect(screen.getByLabelText("Diferença da edição")).toHaveTextContent("R$ 210");
  });

  it("sem decisões não ocupa espaço", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    const { container } = render(<ReviewHistory runId="r2" />, { wrapper });
    await vi.waitFor(() => expect(client.GET).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
