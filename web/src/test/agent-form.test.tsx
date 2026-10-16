import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentEditPage from "@/app/agents/[id]/page";
import { Toaster } from "@/components/ui/sonner";

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

// o sonner guarda os toasts em estado global: um toast de teste anterior pode seguir na tela
function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={makeQueryClient()}>
      {children}
      <Toaster />
    </QueryClientProvider>
  );
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
    schema_version: 2 as const,
    model_id: "claude-sonnet-4-6",
    instructions: {
      persona: "Sou um assistente",
      situation: "",
      tone: "",
      objective: "",
      guardrails: "",
    },
    mcp_servers: [],
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
      if ((path as string).includes("versions")) {
        return { data: [], error: undefined } as never;
      }
      if ((path as string).includes("usage/rollup")) {
        return { data: [], error: undefined } as never;
      }
      if ((path as string).endsWith("/teams")) {
        return { data: [], error: undefined } as never;
      }
      if ((path as string).includes("knowledge-bases")) {
        return { data: [], error: undefined } as never;
      }
      if ((path as string).includes("mcp-servers")) {
        return { data: [], error: undefined } as never;
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
      expect(screen.getAllByText("Rascunho salvo")[0]).toBeInTheDocument();
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
      expect(screen.getAllByText("Erro ao salvar rascunho")[0]).toBeInTheDocument();
    });
  });

  it("marca alterações não salvas e limpa ao salvar", async () => {
    render(<AgentEditPage />, { wrapper });
    const nameInput = await screen.findByDisplayValue("Agente Teste");
    expect(screen.queryByText(/alterações não salvas/i)).not.toBeInTheDocument();

    await userEvent.type(nameInput, " 2");
    expect(screen.getByText(/alterações não salvas/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /salvar rascunho/i }));
    await waitFor(() => {
      expect(screen.getAllByText("Rascunho salvo")[0]).toBeInTheDocument();
    });
    expect(screen.queryByText(/alterações não salvas/i)).not.toBeInTheDocument();
    expect(screen.getByDisplayValue("Agente Teste 2")).toBeInTheDocument();
  });

  it("pede confirmação ao sair com alterações não salvas", async () => {
    window.history.pushState({}, "", "/agents/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<AgentEditPage />, { wrapper });
    const nameInput = await screen.findByDisplayValue("Agente Teste");
    await userEvent.type(nameInput, " 2");

    await userEvent.click(screen.getByRole("link", { name: "Voltar" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(window.location.pathname).toBe("/agents/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    confirm.mockRestore();
    window.history.pushState({}, "", "/");
  });

  it("exibe erro quando o agente não carrega", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: undefined, error: { detail: "x" } } as never);
    render(<AgentEditPage />, { wrapper });
    expect(await screen.findByText("Erro ao carregar o agente.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeInTheDocument();
  });

  it("organiza a página em abas e mantém o painel de teste visível", async () => {
    render(<AgentEditPage />, { wrapper });
    await screen.findByDisplayValue("Agente Teste");
    for (const name of [/configuração/i, /execuções/i, /desempenho/i, /versões/i]) {
      expect(screen.getByRole("tab", { name })).toBeInTheDocument();
    }
    expect(screen.getByRole("complementary", { name: "Testar" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("tab", { name: /versões/i }));
    expect(await screen.findByText("Nenhuma versão salva.")).toBeInTheDocument();
    // o form continua montado: salvar funciona fora da aba de configuração
    await userEvent.click(screen.getByRole("button", { name: /salvar rascunho/i }));
    await waitFor(() => {
      expect(client.PUT).toHaveBeenCalled();
    });
  });
});
