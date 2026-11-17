import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentsPage from "@/app/page";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

const emptyPage = { items: [], total: 0, page: 1, page_size: 20 };

const mockPage = {
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      name: "Agente Alpha",
      description: "Desc do agente",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-06-01T00:00:00Z",
      current_version: {
        id: "22222222-2222-2222-2222-222222222222",
        version_number: 3,
        label: null,
        status: "published" as const,
        author: "dev",
        created_at: "2025-06-01T00:00:00Z",
      },
      draft_version: null,
    },
    {
      id: "33333333-3333-3333-3333-333333333333",
      name: "Agente Beta",
      description: null,
      created_at: "2025-02-01T00:00:00Z",
      updated_at: "2025-07-01T00:00:00Z",
      current_version: null,
      draft_version: {
        id: "44444444-4444-4444-4444-444444444444",
        version_number: 1,
        label: null,
        status: "draft" as const,
        author: "dev",
        created_at: "2025-07-01T00:00:00Z",
      },
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.mocked(client.GET).mockResolvedValue({ data: emptyPage, error: undefined } as never);
  });

  it("exibe estado de carregamento", () => {
    render(<AgentsPage />, { wrapper });
    expect(screen.getByText("Carregando…")).toBeInTheDocument();
  });

  it("renderiza lista de agentes", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: mockPage, error: undefined } as never);
    render(<AgentsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Agente Alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("Agente Beta")).toBeInTheDocument();
  });

  it("exibe badge da versão publicada", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: mockPage, error: undefined } as never);
    render(<AgentsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/v3/)).toBeInTheDocument();
    });
  });

  it("exibe badge de rascunho", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: mockPage, error: undefined } as never);
    render(<AgentsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText(/rascunho/i)).toBeInTheDocument();
    });
  });

  it("instância vazia mostra os passos e cria a partir de exemplo (UX-02)", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) =>
      path === "/api/v1/templates"
        ? {
            data: [
              {
                key: "atendimento-ao-cliente",
                name: "Atendimento ao Cliente",
                description: "Resolução de dúvidas",
                model_id: "claude-haiku-4-5",
              },
            ],
          }
        : { data: { items: [], total: 0, page: 1, page_size: 12 } }) as never);
    vi.mocked(client.POST).mockResolvedValue({ data: { id: "novo" } } as never);
    render(<AgentsPage />, { wrapper });

    expect(await screen.findByText("Seu primeiro agente")).toBeInTheDocument();
    await userEvent.click(
      await screen.findByRole("button", { name: "Criar a partir de Atendimento ao Cliente" }),
    );
    await waitFor(() =>
      expect(client.POST).toHaveBeenCalledWith("/api/v1/templates/{key}", {
        params: { path: { key: "atendimento-ao-cliente" } },
      }),
    );
  });

  it("viewer não vê o botão de criar agente (UX-06)", async () => {
    vi.mocked(client.GET).mockImplementation((async (path: string) =>
      path === "/api/v1/me"
        ? { data: { id: "v", email: "v@x.com", role: "viewer", scopes: ["configs:read"] } }
        : { data: mockPage }) as never);
    render(<AgentsPage />, { wrapper });

    await waitFor(() => expect(screen.getByText(/rascunho/i)).toBeInTheDocument());
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /novo agente/i })).not.toBeInTheDocument(),
    );
  });

  it("exibe mensagem de erro quando a API falha", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: undefined,
      error: { detail: "erro" },
    } as never);
    render(<AgentsPage />, { wrapper });

    await waitFor(() => {
      expect(screen.getByText("Erro ao carregar agentes.")).toBeInTheDocument();
    });
  });
});
