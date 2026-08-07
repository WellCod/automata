import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LintPanel } from "@/components/lint-panel";
import type { components } from "@/lib/api/schema.d.ts";

vi.mock("@/lib/api/client", () => ({
  default: { POST: vi.fn() },
}));

import client from "@/lib/api/client";

type ConfigPayload = components["schemas"]["ConfigPayload"];

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

const mockPayload: ConfigPayload = {
  schema_version: 1,
  model_id: "claude-sonnet-4-6",
  instructions: { persona: "Assistente", situation: "", tone: "", objective: "", guardrails: "" },
  tools: [],
  capabilities: { extended_thinking: false, structured_output: false, vision: false },
  metadata: {},
};

describe("LintPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.POST).mockResolvedValue({ data: [], error: undefined } as never);
  });

  it("renderiza o botão verificar", () => {
    render(<LintPanel getPayload={() => mockPayload} />, { wrapper });
    expect(screen.getByRole("button", { name: /verificar/i })).toBeInTheDocument();
  });

  it("exibe 'Sem avisos' quando linter não retorna warnings", async () => {
    render(<LintPanel getPayload={() => mockPayload} />, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: /verificar/i }));
    await waitFor(() => {
      expect(screen.getByText("Sem avisos")).toBeInTheDocument();
    });
  });

  it("exibe warnings retornados pelo linter", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: [
        { section: "persona", code: "W001", message: "Persona muito curta", severity: "warning" },
        { section: "objective", code: "W002", message: "Objetivo ausente", severity: "warning" },
      ],
      error: undefined,
    } as never);

    render(<LintPanel getPayload={() => mockPayload} />, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: /verificar/i }));

    await waitFor(() => {
      expect(screen.getByText("persona")).toBeInTheDocument();
    });
    expect(screen.getByText("W001")).toBeInTheDocument();
    expect(screen.getByText("Persona muito curta")).toBeInTheDocument();
    expect(screen.getByText("objective")).toBeInTheDocument();
    expect(screen.getByText("W002")).toBeInTheDocument();
    expect(screen.getByText("Objetivo ausente")).toBeInTheDocument();
  });

  it("exibe erro quando a API falha", async () => {
    vi.mocked(client.POST).mockResolvedValue({
      data: undefined,
      error: { detail: "erro interno" },
    } as never);

    render(<LintPanel getPayload={() => mockPayload} />, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: /verificar/i }));

    await waitFor(() => {
      expect(screen.getByText("Erro ao executar linter.")).toBeInTheDocument();
    });
  });

  it("não chama a API quando getPayload retorna null", async () => {
    render(<LintPanel getPayload={() => null} />, { wrapper });
    await userEvent.click(screen.getByRole("button", { name: /verificar/i }));

    await waitFor(() => {
      expect(screen.getByText("Erro ao executar linter.")).toBeInTheDocument();
    });
    expect(client.POST).not.toHaveBeenCalled();
  });
});
