import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RunTrace } from "@/components/run-trace";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn() },
}));

import client from "@/lib/api/client";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const span = (id: string, type: string, name: string, spans: unknown[] = []) => ({
  id,
  type,
  name,
  duration: "1.2s",
  status: "OK",
  start_time: "2026-10-15T00:00:00Z",
  end_time: "2026-10-15T00:00:01Z",
  spans,
});

describe("RunTrace", () => {
  it("mostra a árvore time → agente → tool", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: {
        trace_id: "t",
        run_id: "r",
        status: "OK",
        duration: "2.5s",
        total_spans: 3,
        error_count: 0,
        tree: [
          span("1", "TEAM", "atendimento.arun", [
            span("2", "AGENT", "consulta-crm.arun", [span("3", "TOOL", "crm_buscar_cliente")]),
          ]),
        ],
      },
      error: undefined,
      response: { status: 200 },
    } as never);

    render(<RunTrace runId="r" />, { wrapper });
    expect(await screen.findByText("atendimento.arun")).toBeInTheDocument();
    expect(screen.getByText("consulta-crm.arun")).toBeInTheDocument();
    expect(screen.getByText("crm_buscar_cliente")).toBeInTheDocument();
    expect(screen.getByText(/3 etapas/)).toBeInTheDocument();
  });

  it("mostra os documentos consultados numa busca em base", async () => {
    const output = JSON.stringify({
      base: "RH",
      trechos: [{ documento: "ferias", fonte: "ferias.pdf", content_id: "c1", texto: "x" }],
    });
    vi.mocked(client.GET).mockResolvedValue({
      data: {
        trace_id: "t",
        run_id: "r2",
        status: "OK",
        duration: "1s",
        total_spans: 2,
        error_count: 0,
        tree: [span("1", "AGENT", "rh.arun", [{ ...span("2", "TOOL", "buscar_rh"), output }])],
      },
      error: undefined,
      response: { status: 200 },
    } as never);

    render(<RunTrace runId="r2" />, { wrapper });
    expect(await screen.findByText("buscar_rh")).toBeInTheDocument();
    expect(
      screen.getByText((_, el) => el?.tagName === "P" && el.textContent === "fontes: ferias"),
    ).toBeInTheDocument();
  });

  it("explica quando não há trace", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: undefined,
      error: { detail: "x" },
      response: { status: 404 },
    } as never);
    render(<RunTrace runId="r" />, { wrapper });
    expect(await screen.findByText(/tracing desligado/)).toBeInTheDocument();
  });
});
