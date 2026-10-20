import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkflowEditor } from "@/components/workflow-editor";
import { MAX_BRANCHES, newNode, structureErrors, type WorkflowNode } from "@/lib/workflow-tree";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function Harness({
  initial = [],
  onValue,
}: {
  initial?: WorkflowNode[];
  onValue: (v: WorkflowNode[]) => void;
}) {
  const [value, setValue] = useState<WorkflowNode[]>(initial);
  return (
    <WorkflowEditor
      value={value}
      onChange={(v) => {
        setValue(v);
        onValue(v);
      }}
    />
  );
}

const last = (fn: ReturnType<typeof vi.fn>) => fn.mock.calls.at(-1)![0] as WorkflowNode[];

describe("estrutura do workflow", () => {
  it("nomes novos não repetem nenhum nome da árvore", () => {
    const cond = newNode("condition", new Set(["etapa"]));
    expect(cond.type === "condition" && cond.steps[0].name).toBe("etapa 2");
    const par = newNode("parallel", new Set(["ramo"]));
    expect(par.type === "parallel" && par.branches.map((b) => b.name)).toEqual([
      "ramo 2",
      "ramo 3",
    ]);
  });

  it("acusa o que a API recusaria", () => {
    const step: WorkflowNode = { type: "step", name: "a", on_error: "stop", max_retries: 0 };
    expect(structureErrors([])).toContain("Adicione ao menos uma etapa.");
    expect(structureErrors([step])).toContain('Escolha o agente ou time de "a".');
    const ok = { ...step, agent_id: "x" };
    expect(structureErrors([ok])).toEqual([]);
    expect(structureErrors([ok, ok])).toContain('Nome repetido: "a".');
    const par = newNode("parallel", new Set(["a"]));
    expect(structureErrors([ok, par]).join(" ")).toMatch(/terminar num paralelo/);
    const cond: WorkflowNode = {
      type: "condition",
      name: "c",
      rule: { kind: "contains", source: "input", value: " " },
      steps: [{ ...ok, name: "b" }],
    };
    expect(structureErrors([cond, ok])).toContain('Preencha o texto da regra de "c".');
  });
});

describe("WorkflowEditor", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation(async (_path: string, init?: unknown) => {
      const kind = (init as { params: { query: { kind: string } } }).params.query.kind;
      const items =
        kind === "agent"
          ? [
              { id: "a1", name: "Triagem" },
              { id: "a2", name: "Financeiro" },
            ]
          : [{ id: "t1", name: "Time jurídico" }];
      return { data: { items, total: items.length }, error: undefined } as never;
    });
  });

  it("monta triagem, paralelo e condição sobre a mensagem", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness onValue={onValue} />, { wrapper });

    await user.click(screen.getByRole("button", { name: "Etapa" }));
    await screen.findByRole("option", { name: "Triagem" });
    await user.selectOptions(screen.getByLabelText("Quem executa etapa"), "agent:a1");

    await user.click(screen.getByRole("button", { name: "Paralelo" }));
    await user.selectOptions(screen.getByLabelText("Quem executa ramo"), "agent:a2");
    await user.selectOptions(screen.getByLabelText("Quem executa ramo 2"), "team:t1");
    expect(screen.getByText(/terminar num paralelo/)).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Condição" }).at(-1)!);
    await user.type(screen.getByLabelText("Texto da regra de condição"), "reembolso");
    await user.selectOptions(screen.getByLabelText("Quem executa etapa 2"), "agent:a2");

    const steps = last(onValue);
    expect(steps.map((n) => n.type)).toEqual(["step", "parallel", "condition"]);
    expect(steps[0]).toMatchObject({ agent_id: "a1", team_id: null });
    expect(steps[1]).toMatchObject({
      branches: [{ agent_id: "a2" }, { team_id: "t1", agent_id: null }],
    });
    expect(steps[2]).toMatchObject({
      rule: { kind: "contains", source: "input", value: "reembolso" },
      steps: [{ name: "etapa 2", agent_id: "a2" }],
    });
    expect(screen.queryByLabelText("Pendências")).toBeNull();
  });

  it("paralelo tem de 2 a 5 ramos e só aceita etapas", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness initial={[newNode("parallel", new Set())]} onValue={onValue} />, { wrapper });
    const par = screen.getByRole("listitem", { name: "Paralelo paralelo" });
    expect(within(par).getByRole("button", { name: "Remover ramo" })).toBeDisabled();
    expect(within(par).queryByRole("button", { name: "Condição" })).toBeNull();
    for (let i = 2; i < MAX_BRANCHES; i += 1) {
      await user.click(within(par).getByRole("button", { name: "Ramo" }));
    }
    const value = last(onValue)[0];
    expect(value.type === "parallel" && value.branches).toHaveLength(MAX_BRANCHES);
    expect(within(par).queryByRole("button", { name: "Ramo" })).toBeNull();
  });

  it("repetição com regra de parada, reordenação e limite de aninhamento", async () => {
    const onValue = vi.fn();
    const user = userEvent.setup();
    render(<Harness onValue={onValue} />, { wrapper });
    await user.click(screen.getByRole("button", { name: "Etapa" }));
    await user.click(screen.getAllByRole("button", { name: "Repetição" }).at(-1)!);

    await user.click(screen.getByLabelText("Parar antes quando a resposta cumprir uma regra"));
    await user.type(screen.getByLabelText("Texto da regra de repetição"), "pronto");
    await user.click(screen.getByRole("button", { name: "Subir repetição" }));
    const steps = last(onValue);
    expect(steps.map((n) => n.name)).toEqual(["repetição", "etapa"]);
    expect(steps[0]).toMatchObject({
      max_iterations: 3,
      until: { kind: "contains", source: "previous", value: "pronto" },
    });

    // nível 2 aceita contêiner; dentro dele (nível 3) só etapa
    const loop = screen.getByRole("listitem", { name: "Repetição repetição" });
    await user.click(within(loop).getAllByRole("button", { name: "Condição" }).at(-1)!);
    const cond = screen.getByRole("listitem", { name: "Condição condição" });
    expect(within(cond).queryByRole("button", { name: "Paralelo" })).toBeNull();
    expect(within(cond).getAllByRole("button", { name: "Etapa" }).length).toBeGreaterThan(0);
  });
});
