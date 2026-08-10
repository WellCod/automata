import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VersionsPanel } from "@/components/versions-panel";

vi.mock("@/lib/api/client", () => ({
  default: { GET: vi.fn(), POST: vi.fn() },
}));

import client from "@/lib/api/client";

const AGENT_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

const basePayload = {
  schema_version: 1 as const,
  model_id: "claude-sonnet-4-6",
  instructions: { persona: "A", situation: "", tone: "", objective: "", guardrails: "" },
  tools: [],
  capabilities: { extended_thinking: false, structured_output: false, vision: false },
  metadata: {},
};

const mockVersions = [
  {
    id: "v3",
    version_number: 3,
    label: null,
    status: "draft",
    author: "panel",
    created_at: "2025-06-03T10:00:00Z",
    payload: { ...basePayload, model_id: "claude-opus-4-7" },
  },
  {
    id: "v2",
    version_number: 2,
    label: null,
    status: "published",
    author: "panel",
    created_at: "2025-06-02T10:00:00Z",
    payload: basePayload,
  },
  {
    id: "v1",
    version_number: 1,
    label: null,
    status: "published",
    author: "panel",
    created_at: "2025-06-01T10:00:00Z",
    payload: basePayload,
  },
];

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={makeQueryClient()}>{children}</QueryClientProvider>;
}

describe("VersionsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(client.GET).mockResolvedValue({ data: mockVersions, error: undefined } as never);
    vi.mocked(client.POST).mockResolvedValue({
      data: {
        id: "v2",
        version_number: 2,
        label: null,
        status: "published",
        author: "panel",
        created_at: "2025-06-02T10:00:00Z",
      },
      error: undefined,
    } as never);
  });

  it("exibe a lista de versões", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("v3")).toBeInTheDocument();
    });
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
  });

  it("exibe botão publicar quando há rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publicar/i })).toBeInTheDocument();
    });
  });

  it("não exibe botão publicar sem rascunho", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: [mockVersions[1], mockVersions[2]],
      error: undefined,
    } as never);
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("v2")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /publicar/i })).not.toBeInTheDocument();
  });

  it("exibe diff de campos alterados no rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText(/modelo:/i)).toBeInTheDocument();
    });
  });

  it("exibe botão reverter em versão publicada anterior", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reverter/i })).toBeInTheDocument();
    });
  });

  it("chama publish ao clicar em publicar rascunho", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publicar/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /publicar/i }));
    await waitFor(() => {
      expect(client.POST).toHaveBeenCalledWith(
        "/api/v1/configs/{config_id}/publish",
        expect.objectContaining({ params: { path: { config_id: AGENT_ID } } }),
      );
    });
  });

  it("chama rollback ao clicar em reverter", async () => {
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /reverter/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole("button", { name: /reverter/i }));
    await waitFor(() => {
      expect(client.POST).toHaveBeenCalledWith(
        "/api/v1/configs/{config_id}/rollback",
        expect.objectContaining({
          params: { path: { config_id: AGENT_ID } },
          body: { version_id: "v1" },
        }),
      );
    });
  });

  it("exibe estado de lista vazia", async () => {
    vi.mocked(client.GET).mockResolvedValue({ data: [], error: undefined } as never);
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Nenhuma versão salva.")).toBeInTheDocument();
    });
  });

  it("exibe erro quando API falha", async () => {
    vi.mocked(client.GET).mockResolvedValue({
      data: undefined,
      error: { detail: "erro" },
    } as never);
    render(<VersionsPanel agentId={AGENT_ID} />, { wrapper });
    await waitFor(() => {
      expect(screen.getByText("Erro ao carregar versões.")).toBeInTheDocument();
    });
  });
});
