import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AlertsPage from "@/app/alertas/page";
import { BudgetSection } from "@/components/budget-section";
import { blockLabel } from "@/lib/guardrail-labels";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn(), PUT: vi.fn(), DELETE: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const budget = {
  monthly_usd: 10,
  alert_percent: 80,
  hard_stop: false,
  period: "202610",
  spent_usd: 8.5,
  percent: 85,
  level: "warning",
} as const;

const destination = {
  id: "d1",
  name: "#operacao",
  host: "hooks.slack.com",
  events: ["errors.spike"],
  created_by: "owner",
  last_status: null,
  last_at: null,
  created_at: "2026-10-21T10:00:00Z",
} as const;

describe("BudgetSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: budget, error: undefined } as never);
    vi.mocked(client.PUT).mockResolvedValue({
      data: { ...budget, hard_stop: true },
      error: undefined,
    } as never);
  });

  it("mostra o gasto do mês sobre o limite e o nível", async () => {
    render(<BudgetSection configId="a1" />, { wrapper });
    const status = await screen.findByRole("status");
    // a moeda do Intl separa o símbolo com espaço não separável
    expect(status).toHaveTextContent(/US\$\s8,50 gastos de US\$\s10,00/);
    expect(status).toHaveTextContent("perto do limite");
    expect(screen.getByRole("meter", { name: "Gasto sobre o orçamento" })).toHaveAttribute(
      "aria-valuenow",
      "85",
    );
  });

  it("salva limite com vírgula, aviso e bloqueio", async () => {
    const user = userEvent.setup();
    render(<BudgetSection configId="a1" />, { wrapper });
    const limit = await screen.findByLabelText("Limite em US$");
    await user.clear(limit);
    await user.type(limit, "12,5");
    await user.click(screen.getByLabelText("Barrar runs ao estourar"));
    await user.click(screen.getByRole("button", { name: "Salvar orçamento" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    expect(vi.mocked(client.PUT).mock.calls[0][1]).toEqual({
      params: { path: { config_id: "a1" } },
      body: { monthly_usd: 12.5, alert_percent: 80, hard_stop: true },
    });
  });

  it("sem limite manda vazio", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: { ...budget, monthly_usd: null, percent: null, level: null },
      error: undefined,
    } as never);
    const user = userEvent.setup();
    render(<BudgetSection configId="a1" />, { wrapper });
    expect(await screen.findByLabelText("Limite em US$")).toHaveValue("");
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Salvar orçamento" }));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    expect(
      (vi.mocked(client.PUT).mock.calls[0][1] as { body: { monthly_usd: unknown } }).body
        .monthly_usd,
    ).toBeNull();
  });

  it("bloqueio por orçamento tem nome próprio", () => {
    expect(blockLabel("budget_exceeded")).toBe("Orçamento do mês");
  });
});

describe("página de alertas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: [destination], error: undefined } as never);
    vi.mocked(client.PUT).mockResolvedValue({ data: destination, error: undefined } as never);
    vi.mocked(client.POST).mockResolvedValue({
      data: { ...destination, id: "d2", name: "#financeiro", secret: "segredo-uma-vez" },
      error: undefined,
    } as never);
  });

  it("cadastra destino com os eventos marcados e mostra o segredo uma vez", async () => {
    const user = userEvent.setup();
    render(<AlertsPage />, { wrapper });
    await user.type(screen.getByLabelText("Nome"), "#financeiro");
    await user.type(screen.getByLabelText("URL do webhook"), "https://hooks.slack.com/x");
    const novo = screen.getByRole("group", { name: "Eventos do novo destino" });
    await user.click(within(novo).getByLabelText("Pico de erro"));
    await user.click(screen.getByRole("button", { name: "Cadastrar destino" }));

    await waitFor(() => expect(client.POST).toHaveBeenCalled());
    expect(vi.mocked(client.POST).mock.calls[0][1]).toEqual({
      body: {
        name: "#financeiro",
        url: "https://hooks.slack.com/x",
        events: ["budget.warning", "budget.exceeded", "errors.spike"],
      },
    });
    const dialog = await screen.findByRole("alertdialog", { name: "Segredo do destino" });
    expect(dialog).toHaveTextContent("segredo-uma-vez");
    await user.click(screen.getByRole("button", { name: "Já guardei" }));
    expect(screen.queryByText("segredo-uma-vez")).not.toBeInTheDocument();
  });

  it("lista só o host e troca os eventos assinados", async () => {
    const user = userEvent.setup();
    render(<AlertsPage />, { wrapper });
    const row = await screen.findByRole("group", { name: "Eventos de #operacao" });
    expect(screen.getByText("hooks.slack.com")).toBeInTheDocument();
    await user.click(within(row).getByLabelText("Orçamento estourado"));
    await waitFor(() => expect(client.PUT).toHaveBeenCalled());
    expect(vi.mocked(client.PUT).mock.calls[0][1]).toEqual({
      params: { path: { destination_id: "d1" } },
      body: { name: "#operacao", events: ["errors.spike", "budget.exceeded"] },
    });
  });
});
