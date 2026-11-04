import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CallerBudgetEditor } from "@/components/caller-budget";
import { DEFAULT_RUN, type RunControls, RunControlsEditor } from "@/components/run-controls-editor";
import { EVENT_LABELS } from "@/lib/alert-events";
import { stopLabel } from "@/lib/guardrail-labels";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

const SUBJECT = "integration:11111111-1111-1111-1111-111111111111";

const budget = {
  subject: SUBJECT,
  label: "loja",
  kind: "integration",
  monthly_usd: 10,
  warn_percent: 80,
  hard_stop: true,
  spent_usd: 8.5,
  percent: 85,
  level: "warning",
  updated_at: "2026-11-04T12:00:00Z",
};

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("orçamento por quem chama", () => {
  it("mostra o gasto do mês e edita com bloqueio", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [budget], error: undefined } as never);
    vi.mocked(client.PUT).mockResolvedValue({ data: budget, error: undefined } as never);
    const user = userEvent.setup();
    render(<CallerBudgetEditor subject={SUBJECT} label="loja" />, { wrapper });
    expect(await screen.findByText(/de US\$\s*10,00 no mês \(85%\)/)).toBeInTheDocument();
    expect(screen.getByText(/bloqueia ao estourar/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Orçamento de loja" }));
    const group = screen.getByRole("group", { name: "Orçamento de loja" });
    const limit = within(group).getByLabelText("Limite do mês em dólar");
    await user.clear(limit);
    await user.type(limit, "25");
    await user.click(within(group).getByLabelText("Bloquear ao estourar"));
    await user.click(within(group).getByRole("button", { name: "Salvar orçamento" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    const [path, opts] = vi.mocked(client.PUT).mock.calls[0] as unknown as [
      string,
      { params: { path: { subject: string } }; body: unknown },
    ];
    expect(path).toBe("/api/v1/caller-budgets/{subject}");
    expect(opts.params.path.subject).toBe(SUBJECT);
    expect(opts.body).toEqual({ monthly_usd: 25, warn_percent: 80, hard_stop: false });
  });

  it("sem orçamento oferece definir, e o limite vazio não salva", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    const user = userEvent.setup();
    render(<CallerBudgetEditor subject="u1" label="ana@exemplo.com" />, { wrapper });
    expect(await screen.findByText("Sem orçamento")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Orçamento de ana@exemplo.com" }));
    expect(screen.getByRole("button", { name: "Salvar orçamento" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Remover orçamento" })).toBeNull();
  });
});

describe("teto de custo por resposta", () => {
  it("liga com o padrão e muda o valor", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: {}, error: undefined } as never);
    const seen: RunControls[] = [];
    function Harness() {
      const [value, setValue] = useState<RunControls>(DEFAULT_RUN);
      return (
        <RunControlsEditor
          value={value}
          onChange={(v) => {
            seen.push(v);
            setValue(v);
          }}
          modelId="claude-sonnet-4-6"
          capabilities={{ extended_thinking: false, structured_output: false, vision: false }}
        />
      );
    }
    const user = userEvent.setup();
    render(<Harness />, { wrapper });
    await user.click(screen.getByLabelText(/Limitar o custo de cada resposta/));
    expect(seen.at(-1)?.max_cost_usd).toBe(0.5);
    const input = screen.getByLabelText("Teto de custo por resposta em dólar");
    await user.clear(input);
    await user.type(input, "2");
    expect(seen.at(-1)?.max_cost_usd).toBe(2);
    await user.click(screen.getByLabelText(/Limitar o custo de cada resposta/));
    expect(seen.at(-1)?.max_cost_usd).toBeNull();
  });
});

describe("rótulos", () => {
  it("parada pelo teto e eventos do orçamento de quem chama", () => {
    expect(stopLabel("run_cost_limit")).toBe("Parado pelo teto de custo");
    expect(EVENT_LABELS["caller_budget.exceeded"]).toBe("Orçamento de quem chama estourado");
  });
});
