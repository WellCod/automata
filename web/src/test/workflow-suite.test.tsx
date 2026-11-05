import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvalCaseForm } from "@/components/eval-case-form";
import { EvalSuitePanel } from "@/components/eval-suite-panel";
import { WorkflowEditor } from "@/components/workflow-editor";
import { newNode, structureErrors, templateRefs, type WorkflowNode } from "@/lib/workflow-tree";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(client.GET).mockResolvedValue({ data: { items: [] }, error: undefined } as never);
});

describe("roteador e entrada por etapa", () => {
  it("roteador novo tem dois caminhos e pede o texto das regras", () => {
    const router = newNode("router", new Set()) as Extract<WorkflowNode, { type: "router" }>;
    expect(router.routes).toHaveLength(2);
    expect(router.default).toBeNull();
    const errors = structureErrors([router]);
    expect(errors).toContain('Preencha o texto da regra do caminho "caminho".');
  });

  it("texto de entrada cita só etapas que existem", () => {
    expect(templateRefs("A {etapa:triagem} e {etapa: revisão }")).toEqual(["triagem", "revisão"]);
    const step: WorkflowNode = {
      type: "step",
      name: "revisao",
      agent_id: "a",
      on_error: "stop",
      max_retries: 0,
      input: "template",
      template: "{entrada} {etapa:fantasma}",
    };
    expect(structureErrors([step])).toContain(
      'O texto de "revisao" cita a etapa "fantasma", que não existe.',
    );
  });

  it("adiciona roteador e troca a entrada da etapa no editor", async () => {
    let last: WorkflowNode[] = [];
    function Harness() {
      const [value, setValue] = useState<WorkflowNode[]>([]);
      return (
        <WorkflowEditor
          value={value}
          onChange={(v) => {
            last = v;
            setValue(v);
          }}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />, { wrapper });
    await user.click(screen.getByRole("button", { name: "Roteador" }));
    expect(last[0].type).toBe("router");
    expect(screen.getAllByRole("listitem", { name: /^Caminho / })).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Caminho" }));
    expect(last[0].type === "router" && last[0].routes).toHaveLength(3);
    await user.click(screen.getByLabelText(/Caminho padrão quando nenhuma regra casar/));
    expect(last[0].type === "router" && last[0].default).not.toBeNull();

    await user.click(screen.getAllByRole("button", { name: "Etapa" })[0]);
    const step = last[1];
    await user.selectOptions(
      screen.getByLabelText(`Entrada de ${step.name}`),
      "Recebe um texto montado",
    );
    expect(last[1].type === "step" && last[1].template).toBe("{entrada}");
  });
});

describe("suíte", () => {
  it("checagem de texto numa etapa só no workflow", async () => {
    const onSave = vi.fn();
    const user = userEvent.setup();
    const { unmount } = render(
      <EvalCaseForm kind="workflow" saving={false} onSave={onSave} onCancel={() => {}} />,
    );
    await user.type(screen.getByLabelText(/Nome do caso/), "triagem certa");
    await user.type(screen.getByLabelText(/Mensagem/), "quero trocar");
    await user.type(screen.getByLabelText("Etapa da checagem 1"), "triagem");
    await user.type(screen.getByLabelText("Texto da checagem 1"), "troca");
    await user.click(screen.getByRole("button", { name: /salvar/i }));
    expect(onSave.mock.calls[0][0].checks[0]).toMatchObject({ step: "triagem", value: "troca" });
    expect(screen.getByText(/exige o histórico ligado/)).toBeInTheDocument();
    unmount();
    render(<EvalCaseForm kind="agent" saving={false} onSave={() => {}} onCancel={() => {}} />);
    expect(screen.queryByLabelText("Etapa da checagem 1")).toBeNull();
  });

  it("sugestões das conversas abrem o formulário e salvam", async () => {
    const suggestion = {
      name: "prazo de troca",
      input: "qual o prazo?",
      context: [],
      checks: [{ type: "text", kind: "not_empty", value: "" }],
      judge_criteria: null,
      source_run_id: "r1",
      notes: [],
    };
    vi.mocked(client.GET).mockImplementation((async (path: string) => {
      if (path.endsWith("/eval-cases/suggestions")) return { data: [suggestion], error: undefined };
      if (path.endsWith("/eval-cases")) return { data: [], error: undefined };
      if (path.endsWith("/eval-runs")) return { data: [], error: undefined };
      return { data: null, error: undefined };
    }) as never);
    vi.mocked(client.POST).mockResolvedValue({ data: { id: "c1" }, error: undefined } as never);
    const user = userEvent.setup();
    render(<EvalSuitePanel configId="a1" />, { wrapper });
    await user.click(await screen.findByRole("button", { name: "Sugerir das conversas" }));
    const box = await screen.findByRole("region", { name: "Sugestões das conversas" });
    await user.click(await within(box).findByRole("button", { name: "Revisar" }));
    await user.click(within(box).getByRole("button", { name: /salvar/i }));
    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.POST).mock.calls[0] as unknown as [
      string,
      { body: Record<string, unknown> },
    ];
    expect(path).toBe("/api/v1/configs/{config_id}/eval-cases");
    expect(opts.body.source_run_id).toBe("r1");
  });
});
