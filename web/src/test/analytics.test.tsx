import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AnalyticsPage from "@/app/analytics/page";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe("AnalyticsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mostra erro em vez de zeros quando a API falha", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: undefined, error: { detail: "x" } } as never);
    render(<AnalyticsPage />, { wrapper });
    expect(await screen.findByText("Erro ao carregar o resumo do período.")).toBeInTheDocument();
    expect(screen.getByText("Erro ao carregar o uso por agente.")).toBeInTheDocument();
    expect(screen.queryByText("Conversas")).not.toBeInTheDocument();
  });

  it("mostra o resumo quando a API responde", async () => {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if (path.includes("by-agent")) return { data: [], error: undefined } as never;
      return {
        data: {
          total_runs: 42,
          error_rate: 0.05,
          p50_ms: 800,
          p95_ms: 2500,
          total_tokens: 1200,
          total_cost: 0.5,
        },
        error: undefined,
      } as never;
    });
    render(<AnalyticsPage />, { wrapper });
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("5.0%")).toBeInTheDocument();
  });
});
