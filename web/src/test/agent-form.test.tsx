import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentEditPage from "@/app/agents/[id]/page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), PUT: vi.fn() },
}));

import client from "@/lib/api/client";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

const mockDetail = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  name: "Agente Teste",
  description: "Descrição do agente",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-06-01T00:00:00Z",
  current_version: null,
  draft_version: null,
  payload: {
    schema_version: 1 as const,
    model_id: "claude-sonnet-4-6",
    instructions: {
      persona: "Sou um assistente",
      situation: "",
      tone: "",
      objective: "",
      guardrails: "",
    },
    tools: [],
    capabilities: { extended_thinking: false, structured_output: false, vision: false },
    metadata: {},
  },
};

const mockCapabilities = {
  "claude-sonnet-4-6": { extended_thinking: false, structured_output: true, vision: true },
};

describe("AgentEditPage", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockImplementation(async (path: string) => {
      if ((path as string).includes("models/capabilities")) {
        return { data: mockCapabilities, error: undefined } as never;
      }
      return { data: mockDetail, error: undefined } as never;
    });
    vi.mocked(client.PUT).mockResolvedValue({
      data: {
        id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        version_number: 1,
        label: null,
        status: "draft",
        author: "panel",
        created_at: "2025-06-01T00:00:00Z",
      },
      error: undefined,
    } as never);
  });

  it("exibe estado de carregamento", () => {
    render(<AgentEditPage />, { wrapper });
    expect(screen.getByText("Carregando…")).toBeInTheDocument();
  });

  it("popula o formulário com dados do agente", async () => {
    render(<AgentEditPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByDisplayValue("Agente Teste")).toBeInTheDocument();
    });
    // model_id agora é um <select> — aguarda a opção estar presente e selecionada
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "claude-sonnet-4-6" })).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue("Sou um assistente")).toBeInTheDocument();
  });

  it("exibe erro de validação quando nome está vazio", async () => {
    render(<AgentEditPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByDisplayValue("Agente Teste")).toBeInTheDocument();
    });

    const nameInput = screen.getByDisplayValue("Agente Teste");
    await userEvent.clear(nameInput);
    await userEvent.click(screen.getByRole("button", { name: /salvar rascunho/i }));

    await waitFor(() => {
      expect(screen.getByText("Nome obrigatório")).toBeInTheDocument();
    });
  });

  it("salva rascunho ao submeter o formulário", async () => {
    render(<AgentEditPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByDisplayValue("Agente Teste")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /salvar rascunho/i }));

    await waitFor(() => {
      expect(screen.getByText("Salvo como rascunho")).toBeInTheDocument();
    });
    expect(client.PUT).toHaveBeenCalledOnce();
  });

  it("exibe erro quando a API de salvar falha", async () => {
    vi.mocked(client.PUT).mockResolvedValue({
      data: undefined,
      error: { detail: "erro" },
    } as never);

    render(<AgentEditPage />, { wrapper });
    await waitFor(() => {
      expect(screen.getByDisplayValue("Agente Teste")).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: /salvar rascunho/i }));

    await waitFor(() => {
      expect(screen.getByText("Erro ao salvar. Tente novamente.")).toBeInTheDocument();
    });
  });
});
