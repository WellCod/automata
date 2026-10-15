import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MetricsCharts } from "@/components/metrics-charts";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const point = (date: string, runs: number, errors: number) => ({
  date,
  total_runs: runs,
  error_count: errors,
  p50_ms: runs ? 800 : null,
  p95_ms: runs ? 2400 : null,
  total_tokens: runs * 100,
  total_cost: runs ? 0.01 * runs : null,
});

describe("MetricsCharts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("pede a série do agente e mostra os três gráficos com tabela", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [point("2026-10-13", 0, 0), point("2026-10-14", 5, 1)],
      error: undefined,
    } as never);
    render(<MetricsCharts range={{ period: "7d" }} agentId="abc" />, { wrapper });

    expect(await screen.findByText("Conversas por dia")).toBeInTheDocument();
    expect(screen.getByText("Tempo de resposta")).toBeInTheDocument();
    expect(screen.getByText("Custo estimado por dia")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "14/10" })).toBeInTheDocument();
    expect(client.GET).toHaveBeenCalledWith("/api/v1/metrics/timeseries", {
      params: { query: { period: "7d", agent_id: "abc" } },
    });
  });

  it("mostra estado vazio quando não há execução no período", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [point("2026-10-13", 0, 0)],
      error: undefined,
    } as never);
    render(<MetricsCharts range={{ period: "7d" }} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Nenhuma execução no período.")).toBeInTheDocument();
    });
  });
});
