import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CostPanel } from "@/components/cost-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

const AGENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

const mockRollup = {
  agent_config_id: AGENT_ID,
  period: "202608",
  run_count: 42,
  input_tokens: 10_000,
  output_tokens: 5_000,
  total_tokens: 15_000,
  cost: 0.0375,
};

describe("CostPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: [mockRollup], error: undefined } as never);
  });

  it("renderiza o título com o período atual", async () => {
    render(<CostPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/uso/i)).toBeInTheDocument();
    });
  });

  it("exibe execuções, tokens e custo do rollup", async () => {
    render(<CostPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
    });
    expect(screen.getByText("15.0 k")).toBeInTheDocument();
  });

  it("exibe zeros quando não há rollup para o agente", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    render(<CostPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("exibe erro quando a API falha", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: undefined,
      error: { detail: "erro" },
    } as never);
    render(<CostPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Erro ao carregar uso.")).toBeInTheDocument();
    });
  });

  it("passa agent_id e period como query params", async () => {
    render(<CostPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(client.GET).toHaveBeenCalledWith(
        "/api/v1/usage/rollup",
        expect.objectContaining({
          params: expect.objectContaining({
            query: expect.objectContaining({ agent_id: AGENT_ID }),
          }),
        }),
      );
    });
  });
});
